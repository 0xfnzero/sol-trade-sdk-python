import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import (
    PoolTradeHint,
    SubscriptionAccountCache,
    CachedAccount,
    CacheReadContext,
    SubscriptionReadiness,
)
from sol_trade_sdk.trading.route_candidates import CandidateRouteGraph


def test_owned_reusable_graph():
    a, b, pool = [Pubkey.new_unique() for _ in range(3)]
    hints = [PoolTradeHint(pool, a, b)]
    graph = CandidateRouteGraph(hints)
    hints.clear()
    assert next(graph.iterate(a, b))[0].output_mint == b
    assert next(graph.iterate(b, a))[0].output_mint == a


def test_attested_observation_preserves_actual_version_and_gap_guard():
    key, owner = Pubkey.new_unique(), Pubkey.new_unique()
    cache = SubscriptionAccountCache()
    cache.update(key, CachedAccount(owner, b"x", 1, 7))
    ready = SubscriptionReadiness("fork", [str(key)])
    with pytest.raises(Exception):
        cache.observed_snapshot(ready, 100)
    ready.mark_validated([str(key)], 0, "fork")
    snapshot = cache.observed_snapshot(ready, 100)
    context = CacheReadContext(100, 0, 0)
    assert snapshot.get(key, context).slot == 1
    assert snapshot.get(key, context).write_version == 7
    with pytest.raises(ValueError):
        cache.snapshot().get(key, context)
    with pytest.raises(ValueError):
        snapshot.get(key, CacheReadContext(99, 0, 0))
    ready.interrupt("gap")
    with pytest.raises(Exception):
        snapshot.get(key, context)
