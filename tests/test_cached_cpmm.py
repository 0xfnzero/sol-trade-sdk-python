from dataclasses import replace
import json
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    CachedCpmmState,
    TokenTransferFee,
    quote_cached_cpmm_exact_in,
    CacheReadContext,
    CachedAccount,
    PoolTradeHint,
    SubscriptionAccountCache,
)
from sol_trade_sdk.instruction.cached_cpmm import PROGRAM, AUTHORITY

TOKEN = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")


def state(case):
    keys = [Pubkey.new_unique() for _ in range(9)]
    fee = TokenTransferFee(case["fee_basis_points"], int(case["maximum_fee"]))
    return CachedCpmmState(
        *keys,
        1000000,
        2000000,
        2500,
        120000,
        40000,
        10000,
        case["creator_fee_on"],
        case["enabled"],
        fee,
        fee,
        0,
    )


def test_rust_golden_quotes():
    cases = json.loads((Path(__file__).parent / "fixtures/cpmm_rust_5_0_6.json").read_text())[
        "cases"
    ]
    for case in cases:
        q = quote_cached_cpmm_exact_in(
            state(case), int(case["amount"]), case["base_in"], case["slippage_bps"]
        )
        assert (q.amount_out, q.minimum_amount_out, q.trade_fee) == tuple(
            int(case[n]) for n in ("amount_out", "minimum_amount_out", "trade_fee")
        )


def fixture():
    c = SubscriptionAccountCache()
    keys = [Pubkey.new_unique() for _ in range(7)]
    pool, config, base, quote, bv, qv, obs = keys
    d = bytearray(637)
    d[:8] = bytes.fromhex("f7ede3f5d7c3de46")
    for o, k in [
        (8, config),
        (72, bv),
        (104, qv),
        (168, base),
        (200, quote),
        (232, TOKEN),
        (264, TOKEN),
        (296, obs),
    ]:
        d[o : o + 32] = bytes(k)
    for o, n in [(341, 10), (357, 20), (397, 5), (373, 100)]:
        d[o : o + 8] = n.to_bytes(8, "little")
    d[389] = 2
    d[390] = 1
    f = bytearray(236)
    f[:8] = bytes.fromhex("daf42168cbcb2b6f")
    for o, n in [(12, 4321), (20, 12345), (28, 54321), (108, 987)]:
        f[o : o + 8] = n.to_bytes(8, "little")
    for k, b in [(pool, d), (config, f)]:
        c.update(k, CachedAccount(PROGRAM, b, 100, 1))
    for vault, mint, amount in [(bv, base, 1000), (qv, quote, 2000)]:
        v = bytearray(165)
        v[:32] = bytes(mint)
        v[32:64] = bytes(AUTHORITY)
        v[64:72] = amount.to_bytes(8, "little")
        v[108] = 1
        m = bytearray(82)
        m[45] = 1
        c.update(vault, CachedAccount(TOKEN, v, 100, 1))
        c.update(mint, CachedAccount(TOKEN, m, 100, 1))
    return c, PoolTradeHint(pool, quote, base), d, bv


def test_state_reserve_fees_orientation_and_validation():
    c, h, d, bv = fixture()
    ctx = CacheReadContext(100, 0, 0)
    p = c.snapshot().cpmm(h, ctx, 100)
    assert (
        p.base_mint,
        p.base_reserve,
        p.quote_reserve,
        p.trade_fee_rate,
        p.creator_fee_rate,
        p.creator_fee_on,
    ) == (h.output_mint, 965, 2000, 4321, 987, 2)
    _, q, ix = c.snapshot().prepare_cpmm(h, ctx, 100, Pubkey.new_unique(), 100, 100)
    assert q.amount_out > 0 and ix.accounts[10].pubkey == h.input_mint
    with pytest.raises(ValueError, match="not open"):
        c.snapshot().cpmm(h, ctx, 99)
    d[329] = 4
    c.update(h.pool, CachedAccount(PROGRAM, d, 100, 2))
    with pytest.raises(ValueError, match="disabled"):
        c.snapshot().cpmm(h, ctx, 100)
    d[329] = 0
    c.update(h.pool, CachedAccount(PROGRAM, d, 100, 3))
    bad = bytearray(165)
    bad[:32] = bytes(h.output_mint)
    bad[32:64] = bytes(AUTHORITY)
    bad[108] = 1
    c.update(bv, CachedAccount(TOKEN, bad, 100, 2))
    with pytest.raises(ValueError, match="unsigned"):
        c.snapshot().cpmm(h, ctx, 100)


def test_mainnet_simulation_outputs_match_current_state_and_token_fees():
    import base64

    root = Path(__file__).parents[1] / "examples/fixtures"
    saved = json.loads((root / "cpmm_mainnet_20261002.json").read_text())
    c = SubscriptionAccountCache()
    for name in ("pool", "config", "base_mint", "quote_mint", "base_vault", "quote_vault"):
        a = saved[name]
        c.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(
                Pubkey.from_string(a["owner"]), base64.b64decode(a["data"]), int(a["slot"]), 0
            ),
        )
    hint = PoolTradeHint(
        Pubkey.from_string(saved["pool"]["pubkey"]),
        Pubkey.from_string(saved["base_mint"]["pubkey"]),
        Pubkey.from_string(saved["quote_mint"]["pubkey"]),
    )
    state = c.snapshot().cpmm(
        hint,
        CacheReadContext(int(saved["read_slot"]), int(saved["epoch"]), 32),
        int(saved["unix_timestamp"]),
    )
    for case in json.loads((root / "cpmm_mainnet_simulations_20261002.json").read_text())["cases"]:
        buy = case["side"] == "buy"
        i, o = int(case["input_reserve_at_simulation"]), int(case["output_reserve_at_simulation"])
        at_simulation = replace(state, base_reserve=i if buy else o, quote_reserve=o if buy else i)
        q = quote_cached_cpmm_exact_in(at_simulation, 1000000 if buy else 1000000000, buy, 100)
        assert q.amount_out == int(case["actual_net_output"])


@pytest.mark.parametrize("field,value", [
    ("enable_creator_fee", 1), ("enable_creator_fee", "false"),
    ("enable_creator_fee", None), ("creator_fee_on", True),
    ("creator_fee_on", 1.0), ("creator_fee_on", "1"),
    ("creator_fee_rate", -1), ("creator_fee_rate", 1 << 64),
    ("creator_fee_rate", True), ("creator_fee_rate", "0"),
])
def test_rejects_untyped_fee_state_even_when_disabled(field, value):
    case = dict(fee_basis_points=0, maximum_fee="0", creator_fee_on=0, enabled=False)
    with pytest.raises(ValueError):
        quote_cached_cpmm_exact_in(replace(state(case), **{field: value}), 100, True)


def test_disabled_creator_fee_keeps_full_u64_range():
    case = dict(fee_basis_points=0, maximum_fee="0", creator_fee_on=0, enabled=False)
    p = state(case)
    assert quote_cached_cpmm_exact_in(replace(p, creator_fee_rate=(1 << 64) - 1), 100, True) == quote_cached_cpmm_exact_in(p, 100, True)


@pytest.mark.parametrize("bps", [True, False])
def test_token_fee_rejects_boolean_basis_points(bps):
    with pytest.raises(ValueError, match="basis points"):
        TokenTransferFee(bps, 100).calculate(100)
