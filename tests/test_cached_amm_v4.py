"""Rust oracle and real AMM v4 V2 execution evidence; no network in tests."""

import base64, json, struct, dataclasses
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedAccount,
    SubscriptionAccountCache,
    PoolTradeHint,
    CacheReadContext,
)
from sol_trade_sdk.trading.cached_amm_v4 import (
    CachedAmmV4State,
    quote_cached_amm_v4_exact_in,
    PROGRAM,
)
from sol_trade_sdk.instruction.raydium_amm_v4_builder import decode_amm_info
from sol_trade_sdk.trading.cached_trade import CachedTradeRequest, prepare_cached_trade

ROOT = Path(__file__).parents[1]


def load(name="buy"):
    return json.loads(
        (
            ROOT / "examples/fixtures" / f"amm_v4_{name}_mainnet_20261002.json"
        ).read_text()
    )


def snapshot(v):
    c = SubscriptionAccountCache()
    for a in v["accounts"]:
        c.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]),
                base64.b64decode(a["data"]),
                int(a["slot"]),
                int(a["write_version"]),
            ),
        )
    return c.snapshot()


def hints(v):
    return tuple(
        PoolTradeHint(
            *(Pubkey.from_string(h[k]) for k in ["pool", "input_mint", "output_mint"])
        )
        for h in v["legs"]
    )


def context(v):
    return CacheReadContext(int(v["read_slot"]), int(v["epoch"]), 0)


VECTORS = json.loads((ROOT / "tests/fixtures/amm_v4_rust_5_0_6.json").read_text())


@pytest.mark.parametrize("v", VECTORS)
def test_rust_actual_fee_quote(v):
    k = Pubkey.default()
    p = CachedAmmV4State(
        k,
        k,
        k,
        k,
        k,
        int(v["coin_reserve"]),
        int(v["pc_reserve"]),
        int(v["numerator"]),
        int(v["denominator"]),
    )
    q = quote_cached_amm_v4_exact_in(
        p, int(v["amount"]), v["coin_in"], v["slippage_bps"]
    )
    assert (q.amount_out, q.minimum_amount_out, q.swap_fee) == tuple(
        int(v[x]) for x in ["out", "min", "fee"]
    )


@pytest.mark.parametrize(
    "v",
    json.loads(
        (ROOT / "tests/fixtures/amm_v4_execution_replays_20261002.json").read_text()
    ),
)
def test_onchain_execution_reprice(v):
    k = Pubkey.default()
    p = CachedAmmV4State(
        k, k, k, k, k, int(v["coin_reserve"]), int(v["pc_reserve"]), 25, 10000
    )
    assert quote_cached_amm_v4_exact_in(
        p, int(v["amount"]), v["coin_in"]
    ).amount_out == int(v["out"])


@pytest.mark.parametrize("name", ["buy", "sell", "route_buy", "route_sell"])
def test_cached_factory_mainnet_fixture(name, monkeypatch):
    import requests

    monkeypatch.setattr(
        requests, "post", lambda *a, **k: pytest.fail("RPC in hot path")
    )
    v = load(name)
    p = prepare_cached_trade(
        CachedTradeRequest(
            v["dex_type"],
            v["trade_type"],
            snapshot(v),
            hints(v),
            context(v),
            int(v["unix_timestamp"]),
            Pubkey.from_string(v["payer"]),
            int(v["amount"]),
            v["recent_blockhash"],
            native_input=v["native_input"],
            native_output=v["native_output"],
            temporary_wsol_seed=v["temporary_wsol_seed"],
            rent_lamports=int(v["rent_lamports"]),
        )
    )
    assert p.route.minimum_net_amount_out == int(v["expected"]["minimum_amount_out"])
    ix = next(ix for ix in p.route.swap_instructions if ix.program_id == PROGRAM)
    assert (
        len(ix.accounts) == 8
        and ix.data[0] == 16
        and ix.accounts[7].is_signer
        and not ix.accounts[7].is_writable
    )
    assert (
        len(p.compiled.message) + p.compiled.required_signatures * 64
        == v["expected"]["wire_bytes"]
    )


def test_decoder_full_u128_and_real_addresses():
    v = load()
    a = next(a for a in v["accounts"] if a["owner"] == str(PROGRAM))
    d = bytearray(base64.b64decode(a["data"]))
    counters = [(1 << 100) + i for i in range(4)]
    for o, n in zip([256, 272, 296, 312], counters):
        d[o : o + 16] = n.to_bytes(16, "little")
    p = decode_amm_info(bytes(d))
    assert [
        p.output.swap_coin_in_amount,
        p.output.swap_pc_out_amount,
        p.output.swap_pc_in_amount,
        p.output.swap_coin_out_amount,
    ] == counters
    assert p.token_coin == Pubkey.from_bytes(
        bytes(d[336:368])
    ) and p.coin_mint == Pubkey.from_bytes(bytes(d[400:432]))


@pytest.mark.parametrize(
    "kind",
    [
        "disabled",
        "future_open",
        "fee",
        "pnl",
        "nonce",
        "vault_owner",
        "vault_mint",
        "frozen",
        "decimals",
        "stale",
        "missing",
    ],
)
def test_reject_invalid_current_state(kind):
    v = load()
    pool = v["legs"][0]["pool"]
    a = next(a for a in v["accounts"] if a["pubkey"] == pool)
    d = bytearray(base64.b64decode(a["data"]))
    coin_vault = str(Pubkey.from_bytes(bytes(d[336:368])))
    coin_mint = str(Pubkey.from_bytes(bytes(d[400:432])))
    if kind == "disabled":
        struct.pack_into("<Q", d, 0, 2)
    if kind == "future_open":
        struct.pack_into("<Q", d, 0, 7)
        struct.pack_into("<Q", d, 224, int(v["unix_timestamp"]) + 1)
    if kind == "fee":
        struct.pack_into("<Q", d, 184, 0)
    if kind == "pnl":
        struct.pack_into("<Q", d, 192, (1 << 64) - 1)
    if kind == "nonce":
        struct.pack_into("<Q", d, 8, 256)
    a["data"] = base64.b64encode(d).decode()
    for vault in v["accounts"]:
        if vault["pubkey"] == coin_vault:
            raw = bytearray(base64.b64decode(vault["data"]))
            if kind == "vault_owner":
                raw[32:64] = bytes(32)
            if kind == "vault_mint":
                raw[:32] = bytes(32)
            if kind == "frozen":
                raw[108] = 2
            vault["data"] = base64.b64encode(raw).decode()
        if vault["pubkey"] == coin_mint and kind == "decimals":
            raw = bytearray(base64.b64decode(vault["data"]))
            raw[44] = 255
            vault["data"] = base64.b64encode(raw).decode()
    if kind == "missing":
        v["accounts"] = [a for a in v["accounts"] if a["pubkey"] != coin_vault]
    ctx = context(v)
    if kind == "stale":
        ctx = dataclasses.replace(ctx, slot=ctx.slot + 1)
    with pytest.raises(ValueError):
        snapshot(v).prepare_amm_v4(
            hints(v)[0],
            ctx,
            int(v["unix_timestamp"]),
            Pubkey.from_string(v["payer"]),
            10000,
            100,
        )
