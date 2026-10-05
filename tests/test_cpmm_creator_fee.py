import base64, json, struct
from pathlib import Path
from types import SimpleNamespace
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import CachedAccount, CacheReadContext, SubscriptionAccountCache
from sol_trade_sdk.instruction import cpmm_creator_fee as f

CASES = json.loads(
    (Path(__file__).parent / "fixtures/cpmm_creator_fee_rust_5_0_7.json").read_text()
)
pk = Pubkey.from_string
raw = lambda a: base64.b64decode(a["data_base64"])


@pytest.mark.parametrize("c", CASES, ids=lambda c: f"{c['name']}-{c['permissionless']}")
def test_rust_mainnet_account_payout_and_cache_parity(c):
    pool = f.decode_cpmm_collection_pool(raw(c["accounts"][0]))
    config = f.decode_cpmm_amm_config(raw(c["accounts"][1]))
    a = c["accounts"][2]
    share = (
        None
        if a is None
        else SimpleNamespace(owner=pk(a["owner"]), data=raw(a), lamports=a["lamports"])
    )
    assert config.creator_fee_share_rate == c["config_share_rate"] and len(config.padding) == 14
    assert str(f.get_creator_fee_share_pda(pool.pool_creator, pool.amm_config)) == c["share_pda"]
    rate = f.resolve_creator_fee_share_rate(config, pool.pool_creator, pool.amm_config, share)
    assert rate == c["share_rate"]
    payer = pk(c["payer"]) if c["permissionless"] else None
    ix = (
        f.collect_creator_fee(pk(c["pool"]), pool)
        if payer is None
        else f.collect_creator_fee_permissionless(payer, pk(c["pool"]), pool)
    )
    assert [str(m.pubkey) for m in ix.accounts] == c["instruction"]["accounts"]
    assert (
        bytes(ix.data) == base64.b64decode(c["instruction"]["data_base64"])
        and str(ix.program_id) == c["instruction"]["program_id"]
    )
    assert [m.is_signer for m in ix.accounts] == [i == 0 for i in range(len(ix.accounts))]
    assert [m.is_writable for m in ix.accounts] == [
        i in (0, 3 if payer else 2, 4, 5, 8, 9) for i in range(len(ix.accounts))
    ]
    for check in c["checks"]:
        assert f.split_creator_fee(int(check["gross"]), rate) == (
            int(check["creator_before_transfer_fee"]),
            int(check["protocol_share"]),
        )
    cache = SubscriptionAccountCache()
    ctx = CacheReadContext(100, 0, 5)
    for a in c["accounts"]:
        cache.update(
            pk(a["pubkey"]) if a else pk(c["share_pda"]),
            CachedAccount(pk(a["owner"]) if a else Pubkey.default(), raw(a) if a else b"", 100, 1),
        )
    snapshot = cache.snapshot()
    p = f.prepare_cpmm_creator_fee_collection(snapshot, pk(c["pool"]), ctx, payer)
    assert p.share_rate == rate
    f.validate_cpmm_creator_fee_collection(snapshot, p, CacheReadContext(101, 0, 5), payer)
    altered = SimpleNamespace(**vars(p))
    altered.creator_payout_token0 += 1
    with pytest.raises(ValueError):
        f.validate_cpmm_creator_fee_collection(snapshot, altered, ctx, payer)
    with pytest.raises(ValueError):
        f.validate_cpmm_creator_fee_collection(snapshot, p, CacheReadContext(99, 0, 5), payer)
    cache.update(
        pk(c["share_pda"]),
        CachedAccount(
            share.owner if share else Pubkey.default(), share.data if share else b"", 100, 2
        ),
    )
    with pytest.raises(ValueError):
        f.validate_cpmm_creator_fee_collection(cache.snapshot(), p, ctx, payer)
    with pytest.raises(ValueError):
        f.prepare_cpmm_creator_fee_collection(
            snapshot, pk(c["pool"]), CacheReadContext(106, 0, 5), payer
        )


def test_share_fallback_boundaries_and_malformed_accounts():
    assert f.split_creator_fee(2**64 - 1, 1000000) == (0, 2**64 - 1)
    assert f.split_creator_fee(1, 50000) == (1, 0)
    for gross, rate in [(-1, 0), (2**64, 0), (1, -1), (1, 1000001), (True, 0)]:
        with pytest.raises(ValueError):
            f.split_creator_fee(gross, rate)
    c = next(x for x in CASES if x["name"] == "override")
    config = f.decode_cpmm_amm_config(raw(c["accounts"][1]))
    pool = f.decode_cpmm_collection_pool(raw(c["accounts"][0]))
    data = bytearray(raw(c["accounts"][2]))
    resolve = lambda owner, d, lamports: f.resolve_creator_fee_share_rate(
        config,
        pool.pool_creator,
        pool.amm_config,
        SimpleNamespace(owner=owner, data=d, lamports=lamports),
    )
    assert resolve(f.PROGRAM, data, 0) == config.creator_fee_share_rate
    assert resolve(Pubkey.default(), b"bad", 1) == config.creator_fee_share_rate
    with pytest.raises(ValueError):
        resolve(f.PROGRAM, data[:144], 1)
    with pytest.raises(ValueError):
        f.resolve_creator_fee_share_rate(
            config,
            Pubkey.default(),
            pool.amm_config,
            SimpleNamespace(owner=f.PROGRAM, data=data, lamports=1),
        )
    struct.pack_into("<Q", data, 73, 0)
    assert resolve(f.PROGRAM, data, 1) == 0
    struct.pack_into("<Q", data, 73, 1000001)
    with pytest.raises(ValueError):
        resolve(f.PROGRAM, data, 1)
    for decode, a, size in [
        (f.decode_cpmm_amm_config, c["accounts"][1], 236),
        (f.decode_cpmm_collection_pool, c["accounts"][0], 637),
        (f.decode_cpmm_creator_fee_share, c["accounts"][2], 145),
    ]:
        with pytest.raises(ValueError):
            decode(raw(a)[: size - 1])
        corrupt = bytearray(raw(a))
        corrupt[0] ^= 1
        with pytest.raises(ValueError):
            decode(corrupt)
    cache = SubscriptionAccountCache()
    for a in c["accounts"][:2]:
        cache.update(pk(a["pubkey"]), CachedAccount(pk(a["owner"]), raw(a), 100, 1))
    with pytest.raises(ValueError, match="Missing"):
        f.prepare_cpmm_creator_fee_collection(
            cache.snapshot(), pk(c["pool"]), CacheReadContext(100, 0, 0)
        )


@pytest.mark.asyncio
async def test_rpc_one_snapshot_and_errors():
    c = CASES[0]
    pool = f.decode_cpmm_collection_pool(raw(c["accounts"][0]))
    calls = []

    class RPC:
        async def get_multiple_accounts(self, keys, commitment):
            calls.append((keys, commitment))
            return SimpleNamespace(
                value=[
                    (
                        None
                        if a is None
                        else SimpleNamespace(
                            owner=pk(a["owner"]), data=raw(a), lamports=a["lamports"]
                        )
                    )
                    for a in c["accounts"][1:3]
                ]
            )

    assert (
        await f.fetch_creator_fee_share_rate(RPC(), pool.pool_creator, pool.amm_config)
        == c["share_rate"]
    )
    assert calls == [([pool.amm_config, pk(c["share_pda"])], "confirmed")]

    class Broken:
        async def get_multiple_accounts(self, *args, **kwargs):
            raise RuntimeError("network")

    with pytest.raises(RuntimeError):
        await f.fetch_creator_fee_share_rate(Broken(), pool.pool_creator, pool.amm_config)


def test_protocol_counter_overflow_and_continuity_guard():
    c = CASES[0]
    cache = SubscriptionAccountCache()
    for a in c["accounts"]:
        key = pk(a["pubkey"]) if a else pk(c["share_pda"])
        data = bytearray(raw(a)) if a else b""
        if str(key) == c["pool"]:
            struct.pack_into("<Q", data, 341, 2**64 - 1)
        cache.update(key, CachedAccount(pk(a["owner"]) if a else Pubkey.default(), data, 100, 1))
    with pytest.raises(ValueError):
        f.prepare_cpmm_creator_fee_collection(
            cache.snapshot(), pk(c["pool"]), CacheReadContext(100, 0, 0)
        )
    snapshot = cache.snapshot()

    # The real snapshot guard must run before account reads.
    def interrupted():
        raise RuntimeError("continuity interrupted")

    from sol_trade_sdk.trading.subscription_cache import AccountCacheSnapshot

    guarded = AccountCacheSnapshot({}, interrupted)
    with pytest.raises(RuntimeError, match="continuity"):
        f.prepare_cpmm_creator_fee_collection(guarded, pk(c["pool"]), CacheReadContext(100, 0, 0))
