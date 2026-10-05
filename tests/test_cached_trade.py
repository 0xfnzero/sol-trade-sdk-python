import base64, json, dataclasses
from pathlib import Path
import pytest
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sol_trade_sdk import (
    CachedAccount,
    CacheReadContext,
    PoolTradeHint,
    SubscriptionAccountCache,
    CachedTradeRequest,
    prepare_cached_trade,
)
from sol_trade_sdk.trading.factory import TradeExecutorFactory
from sol_trade_sdk.trading.params import DexType
from sol_trade_sdk.serialization.v1 import (
    compile_v1_message,
    sign_v1_transaction,
    V1Config,
)

F = Path(__file__).parents[1] / "examples/fixtures"


@pytest.mark.parametrize("dex", ["StonkFun", "LaunchLab", "Bonk"])
@pytest.mark.parametrize("side", ["buy", "sell"])
def test_curve_anchor_rejects_mislabeled_single_leg_side(dex, side):
    r = request(side)
    anchor = r.hints[-1] if side == "buy" else r.hints[0]
    wrong = dataclasses.replace(r, dex_type=dex, trade_type="Sell" if side == "buy" else "Buy", hints=(anchor,), native_input=False, native_output=False)
    with pytest.raises(ValueError, match="anchor direction"):
        prepare_cached_trade(wrong)


def request(direction="buy", venue="dlmm", signer=None):
    v = json.loads(
        (
            F / f"{'dlmm_'if venue=='dlmm'else ''}sol_route_{direction}_mainnet_20261002.json"
        ).read_text()
    )
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
    return CachedTradeRequest(
        DexType.STONK_FUN,
        "Buy" if direction == "buy" else "Sell",
        c.snapshot(),
        tuple(
            PoolTradeHint(
                *(Pubkey.from_string(h[k]) for k in ("pool", "input_mint", "output_mint"))
            )
            for h in v["legs"]
        ),
        CacheReadContext(int(v["read_slot"]), int(v["epoch"]), 0),
        int(v["unix_timestamp"]),
        signer.pubkey() if signer else Pubkey.from_string(v["payer"]),
        int(v["amount"]),
        v["recent_blockhash"],
        native_input=v["native_input"],
        native_output=v["native_output"],
        temporary_wsol_seed=v["temporary_wsol_seed"],
        rent_lamports=int(v["rent_lamports"]),
    )


@pytest.mark.parametrize("direction", ["buy", "sell"])
@pytest.mark.parametrize("venue", ["dlmm", "whirlpool"])
def test_factory_independent_cached_trade(direction, venue, monkeypatch):
    import requests

    monkeypatch.setattr(
        requests,
        "post",
        lambda *a, **k: pytest.fail("implicit RPC in cached preparation"),
    )
    r = request(direction, venue)
    p = TradeExecutorFactory.create_cached_executor(DexType.STONK_FUN).prepare(r)
    assert len(p.route.legs) == 3 and len(p.compiled.message) > 1232
    assert p.required_native_lamports == r.rent_lamports + (r.amount if r.native_input else 0)
    golden = compile_v1_message(
        r.payer,
        p.instructions,
        r.recent_blockhash,
        V1Config(compute_unit_limit=300000, loaded_accounts_data_size_limit=64 * 1024 * 1024),
    )
    assert p.compiled == golden
    assert prepare_cached_trade(dataclasses.replace(r, v1_config=V1Config())).compiled == golden


@pytest.mark.asyncio
async def test_transport_receipt_and_signature_verification():
    signer = Keypair.from_seed(bytes([7]) * 32)
    r = request(signer=signer)
    executor = TradeExecutorFactory.create_cached_executor(DexType.STONK_FUN)
    prepared = executor.prepare(r)
    calls = []

    async def submit(wire, direction):
        calls.append(wire)
        assert direction == "Buy"
        assert wire[: len(prepared.compiled.message)] == prepared.compiled.message
        sig = wire[len(prepared.compiled.message) : len(prepared.compiled.message) + 64]
        Ed25519PublicKey.from_public_bytes(bytes(signer.pubkey())).verify(
            sig, prepared.compiled.message
        )
        import base58

        return base58.b58encode(sig).decode()

    receipt = await executor.execute(r, [signer], submit)
    assert receipt["submitted"] and not receipt["confirmed"] and len(calls) == 1
    with pytest.raises(ValueError, match="Missing V1 signer"):
        await executor.execute(r, [], submit)
    assert len(calls) == 1

    async def wrong(*args):
        return "1" * 64

    with pytest.raises(ValueError, match="signature does not match"):
        await executor.execute(r, [signer], wrong)


@pytest.mark.parametrize(
    "kind",
    ["protocol", "direction", "disconnected", "stale", "native_flags", "wrong_factory"],
)
def test_invalid(kind):
    r = request()
    if kind == "protocol":
        r = dataclasses.replace(r, dex_type="RaydiumClmm")
    if kind == "direction":
        r = dataclasses.replace(r, trade_type="Create")
    if kind == "disconnected":
        r = dataclasses.replace(r, hints=tuple(reversed(r.hints)))
    if kind == "stale":
        r = dataclasses.replace(r, context=CacheReadContext(r.context.slot + 1, r.context.epoch, 0))
    if kind == "native_flags":
        r = dataclasses.replace(r, native_output=True)
    e = TradeExecutorFactory.create_cached_executor(
        DexType.RAYDIUM_CLMM if kind == "wrong_factory" else DexType.STONK_FUN
    )
    with pytest.raises(ValueError):
        e.prepare(r)


TIP_ACCOUNT = Pubkey.from_string("96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5")


@pytest.mark.parametrize("direction", ["buy", "sell"])
def test_tip_before_business_without_rpc(direction, monkeypatch):
    import requests, struct
    from src.instruction.common import SYSTEM_PROGRAM

    monkeypatch.setattr(requests, "post", lambda *a, **k: pytest.fail("implicit RPC"))
    r = request(direction)
    base = prepare_cached_trade(r)
    p = prepare_cached_trade(dataclasses.replace(r, tip_account=TIP_ACCOUNT, tip_lamports=5000))
    assert p.instructions[0].program_id == SYSTEM_PROGRAM
    assert bytes(p.instructions[0].data) == struct.pack("<IQ", 2, 5000)
    accounts = p.instructions[0].accounts
    assert accounts[0].pubkey == r.payer and accounts[0].is_signer and accounts[0].is_writable
    assert (
        accounts[1].pubkey == TIP_ACCOUNT and not accounts[1].is_signer and accounts[1].is_writable
    )
    assert p.instructions[1:] == base.instructions and p.route == base.route
    assert p.required_native_lamports == base.required_native_lamports + 5000
    assert bytes(TIP_ACCOUNT) in p.compiled.account_keys


@pytest.mark.parametrize(
    "fields",
    [
        dict(tip_lamports=5000),
        dict(tip_account=TIP_ACCOUNT),
        dict(tip_account=TIP_ACCOUNT, tip_lamports=-1),
        dict(tip_account=TIP_ACCOUNT, tip_lamports=1 << 64),
        dict(tip_account=TIP_ACCOUNT, tip_lamports=(1 << 64) - 1),
        dict(tip_account=Pubkey.default(), tip_lamports=1),
        dict(tip_account=TIP_ACCOUNT, tip_lamports=True),
    ],
)
def test_invalid_tip(fields):
    with pytest.raises(ValueError):
        prepare_cached_trade(dataclasses.replace(request(), **fields))


def test_tip_payer_and_non_native_endpoints():
    r = request()
    with pytest.raises(ValueError):
        prepare_cached_trade(dataclasses.replace(r, tip_account=r.payer, tip_lamports=1))
    plain = dataclasses.replace(r, native_input=False, native_output=False)
    p = prepare_cached_trade(dataclasses.replace(plain, tip_account=TIP_ACCOUNT, tip_lamports=5000))
    assert (
        p.required_native_lamports == 5000
        and p.instructions[1:] == prepare_cached_trade(plain).instructions
    )

@pytest.mark.parametrize("direction", ["buy", "sell"])
@pytest.mark.parametrize("venue", ["dlmm", "whirlpool"])
def test_candidate_routes_equal_explicit(direction, venue):
    r = request(direction, venue)
    explicit = prepare_cached_trade(r)
    automatic = prepare_cached_trade(dataclasses.replace(r, hints=(), candidates=tuple(reversed(r.hints)), input_mint=r.hints[0].input_mint, output_mint=r.hints[-1].output_mint))
    assert automatic == explicit
    assert prepare_cached_trade(dataclasses.replace(r, candidates=(), input_mint=Pubkey.default())) == explicit

@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["buy", "sell"])
async def test_unified_factory_submits(direction):
    signer = Keypair.from_seed(bytes([7])*32)
    r = request(direction=direction, signer=signer)
    prepared = prepare_cached_trade(r)
    calls = []
    async def submit(wire, trade_type):
        import base58
        calls.append(wire)
        assert wire[:len(prepared.compiled.message)] == prepared.compiled.message
        return base58.b58encode(wire[len(prepared.compiled.message):len(prepared.compiled.message)+64]).decode()
    executor = TradeExecutorFactory.create_executor(DexType.STONK_FUN)
    envelope = dict(request=r, signers=[signer], submit=submit)
    execute = executor.execute_buy if direction == "buy" else executor.execute_sell
    receipt = await execute(envelope)
    assert receipt["success"] and receipt["submitted"] and not receipt["confirmed"]
    assert len(calls) == 1
    wrong = executor.execute_sell if direction == "buy" else executor.execute_buy
    with pytest.raises(ValueError, match="direction mismatch"):
        await wrong(envelope)
    assert len(calls) == 1

@pytest.mark.asyncio
async def test_all_factory_protocols_reject_incomplete_execution():
    for dex in TradeExecutorFactory.get_supported_dex_types():
        executor=TradeExecutorFactory.create_executor(dex)
        for execute in (executor.execute_buy,executor.execute_sell):
            with pytest.raises(ValueError,match="request, signers"):
                await execute({})
