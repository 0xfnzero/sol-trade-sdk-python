import base64
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import CachedAccount, CacheReadContext, PoolTradeHint, SubscriptionAccountCache

TOKEN = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")


def test_batch_overlay_versions_and_iterator_failure():
    cache = SubscriptionAccountCache()
    key, other = Pubkey.new_unique(), Pubkey.new_unique()
    a = lambda version, data: CachedAccount(TOKEN, data, 10, version)
    ctx = CacheReadContext(10, 0, 0)
    cache.update(key, a(1, b"one"))
    frozen = cache.snapshot()
    assert cache.update_many([(key, a(2, b"two")), (key, a(1, b"stale")),
                              (key, a(2, b"two")), (key, a(3, b"three"))]) == 2
    assert cache.snapshot().get(key, ctx).data == b"three"
    assert frozen.get(key, ctx).data == b"one"

    def failing_updates():
        yield key, a(4, b"four")
        yield other, a(1, b"new")
        raise RuntimeError("source failed")

    with pytest.raises(RuntimeError, match="source failed"):
        cache.update_many(failing_updates())
    assert cache.snapshot().get(key, ctx).data == b"three"
    with pytest.raises(ValueError, match="Missing"):
        cache.snapshot().get(other, ctx)
    invalid = SimpleNamespace(owner=TOKEN, data=b"invalid", slot=10, write_version=-1)
    with pytest.raises(ValueError):
        cache.update_many([(key, a(4, b"four")), (other, invalid)])
    assert cache.snapshot().get(key, ctx).data == b"three"


def test_conflict_inside_batch_invalidates_without_commit():
    cache = SubscriptionAccountCache()
    key = Pubkey.new_unique()
    a = lambda version, data: CachedAccount(TOKEN, data, 10, version)
    cache.update(key, a(1, b"one"))
    with pytest.raises(ValueError, match="Conflicting"):
        cache.update_many([(key, a(2, b"two")), (key, a(2, b"conflict"))])
    # Fork reads are intentionally invalidated; inspect storage only to verify
    # the separate atomic rollback invariant.
    assert cache._SubscriptionAccountCache__accounts[key].data == b"one"
    with pytest.raises(ValueError, match="Conflicting"):
        cache.snapshot().get(key, CacheReadContext(10, 0, 0))


def fixture():
    data = json.loads(
        (
            Path(__file__).parents[1] / "examples/fixtures/stonkfun_curve_mainnet_20261002.json"
        ).read_text()
    )
    c = SubscriptionAccountCache()
    for name in ("pool", "global", "platform", "base_mint", "quote_mint"):
        a = data[name]
        c.update(
            Pubkey.from_string(a["pubkey"]),
            CachedAccount(Pubkey.from_string(a["owner"]), base64.b64decode(a["data"]), 100, 1),
        )
    h = PoolTradeHint(
        Pubkey.from_string(data["pool"]["pubkey"]),
        Pubkey.from_string(data["base_mint"]["pubkey"]),
        Pubkey.from_string(data["quote_mint"]["pubkey"]),
    )
    return c, h, data


def test_order_conflict_atomicity_and_snapshot_isolation():
    c = SubscriptionAccountCache()
    k = Pubkey.new_unique()
    other = Pubkey.new_unique()
    buf = bytearray(b"one")
    assert c.update(k, CachedAccount(TOKEN, buf, 100, 1))
    buf[0] = 0
    frozen = c.snapshot()
    assert not c.update(k, CachedAccount(TOKEN, b"one", 100, 1))
    assert not c.update(k, CachedAccount(TOKEN, b"old", 99, 999))
    with pytest.raises(ValueError, match="Conflicting"):
        c.update_many(
            [
                (other, CachedAccount(TOKEN, b"new", 100, 1)),
                (k, CachedAccount(TOKEN, b"conflict", 100, 1)),
            ]
        )
    with pytest.raises(ValueError, match="Conflicting"):
        c.snapshot().get(other, CacheReadContext(100, 0, 0))
    with pytest.raises(ValueError, match="Conflicting"):
        frozen.get(k, CacheReadContext(100, 0, 0))
    with pytest.raises(ValueError, match="Conflicting"):
        c.update(k, CachedAccount(TOKEN, b"two", 100, 2))
    # Explicit fork selection requires a new cache; normal updates still preserve
    # frozen bytes when no version conflict has occurred.
    c = SubscriptionAccountCache()
    c.update(k, CachedAccount(TOKEN, b"one", 100, 1))
    frozen = c.snapshot()
    c.update(k, CachedAccount(TOKEN, b"two", 100, 2))
    assert frozen.get(k, CacheReadContext(100, 0, 0)).data == b"one"
    assert c.snapshot().get(k, CacheReadContext(100, 0, 0)).data == b"two"
    for ctx in (CacheReadContext(99, 0, 10), CacheReadContext(102, 0, 1)):
        with pytest.raises(ValueError, match="future or stale"):
            c.snapshot().get(k, ctx)
    with pytest.raises(ValueError, match="owner"):
        c.snapshot().get(k, CacheReadContext(100, 0, 0), Pubkey.new_unique())


def test_parser_closure_tombstone():
    c = SubscriptionAccountCache()
    k = Pubkey.new_unique()
    event = SimpleNamespace(
        metadata=SimpleNamespace(slot=100),
        write_version=1,
        account=SimpleNamespace(pubkey=str(k), owner=str(TOKEN), data=b"old", lamports=0),
    )
    c.update_from_parser(event)
    assert not c.update(k, CachedAccount(TOKEN, b"resurrect", 99, 999))
    with pytest.raises(ValueError, match="closed"):
        c.snapshot().get(k, CacheReadContext(100, 0, 0))


def test_prepare_real_state_replaces_payer_amount_and_direction():
    c, h, data = fixture()
    ctx = CacheReadContext(100, int(data["epoch"]), 0)
    payer = Pubkey.new_unique()
    accounts, q, ix = c.snapshot().prepare_stonkfun_curve(h, ctx, payer, 1000000000, 100)
    assert q.minimum_amount_out == 1374
    assert ix.accounts[0].pubkey == payer
    assert accounts.quote_mint == h.output_mint
    reverse = PoolTradeHint(h.pool, h.output_mint, h.input_mint)
    _, q, _ = c.snapshot().prepare_stonkfun_curve(reverse, ctx, payer, 10000, 100)
    assert q.minimum_amount_out == 6817301666
    with pytest.raises(ValueError, match="identity"):
        c.snapshot().stonkfun_curve(PoolTradeHint(h.pool, Pubkey.new_unique(), h.output_mint), ctx)
    c.update(h.output_mint, CachedAccount(TOKEN, b"", 101, 1))
    with pytest.raises(ValueError, match="closed"):
        c.snapshot().stonkfun_curve(h, CacheReadContext(101, ctx.epoch, 1))


def test_route_identity_does_not_copy_historical_values():
    c, h, data = fixture()
    leg = {
        "protocol": "LaunchLab",
        "program": data["pool"]["owner"],
        "pool": str(h.pool),
        "input_mint": str(h.input_mint),
        "output_mint": str(h.output_mint),
        "specified_amount": "999999999999",
        "trader": "ignore",
    }
    assert PoolTradeHint.from_route_leg(leg) == h
    leg["program"] = str(TOKEN)
    with pytest.raises(ValueError, match="protocol"):
        PoolTradeHint.from_route_leg(leg)
    leg["program"] = data["pool"]["owner"]
    leg["input_mint"] = None
    with pytest.raises(ValueError, match="unresolved"):
        PoolTradeHint.from_route_leg(leg)
