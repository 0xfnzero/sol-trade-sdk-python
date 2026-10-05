import pytest
from solders.pubkey import Pubkey
from sol_trade_sdk import SubscriptionReadiness, CacheNotReadyError, SubscriptionAccountCache, CachedAccount, CacheReadContext

def test_gaps_and_fork_recovery_invalidate_frozen_snapshots():
    key, owner = Pubkey.new_unique(), Pubkey.new_unique()
    r = SubscriptionReadiness("confirmed/fork-a", [str(key), "clock"])
    c = SubscriptionAccountCache()
    c.update(key, CachedAccount(owner, b"x", 1, 0))
    with pytest.raises(CacheNotReadyError): c.ready_snapshot(r)

    assert not r.mark_validated([str(key)], 0, "confirmed/fork-a")
    assert r.mark_validated(["clock"], 0, "confirmed/fork-a")
    old = c.ready_snapshot(r)
    ctx = CacheReadContext(1, 0, 0)
    assert old.get(key, ctx).data == b"x"
    r.interrupt("gap")
    with pytest.raises(CacheNotReadyError): old.get(key, ctx)
    gen = r.begin_recovery("confirmed/fork-a")
    assert not r.mark_validated([str(key), "clock"], 0, "confirmed/fork-a")
    assert not r.mark_validated([str(key), "clock"], gen, "other-fork")
    assert r.mark_validated([str(key), "clock"], gen, "confirmed/fork-a")
    with pytest.raises(CacheNotReadyError): old.get(key, ctx)
    assert c.ready_snapshot(r).get(key, ctx).data == b"x"
    r.require_accounts(["new-array"])
    with pytest.raises(CacheNotReadyError): c.ready_snapshot(r)

def test_new_array_cannot_bypass_interrupted_fork_recovery():
    r = SubscriptionReadiness("confirmed/fork-a", ["pool"])
    assert r.mark_validated(["pool"], 0, "confirmed/fork-a")
    old_guard = r.guard()
    r.interrupt("fork conflict")
    generation = r.require_accounts(["new-array"])
    assert r.status()["state"] == "continuity-broken"
    assert r.status()["reason"] == "fork conflict"
    assert not r.mark_validated(["pool", "new-array"], generation, "confirmed/fork-a")
    with pytest.raises(CacheNotReadyError): r.guard()
    recovered = r.begin_recovery("confirmed/fork-b")
    assert not r.mark_validated(["pool", "new-array"], generation, "confirmed/fork-a")
    assert not r.mark_validated(["pool"], recovered, "confirmed/fork-b")
    assert r.mark_validated(["new-array"], recovered, "confirmed/fork-b")
    r.guard()()
    with pytest.raises(CacheNotReadyError): old_guard()

@pytest.mark.parametrize("conflict", ["data", "owner", "closed"])
def test_conflict_invalidates_live_bound_and_offline_snapshots(conflict):
    key, owner = Pubkey.new_unique(), Pubkey.new_unique()
    c = SubscriptionAccountCache()
    c.update(key, CachedAccount(owner, b"one", 1, 0))
    r = SubscriptionReadiness("confirmed/fork-a", [str(key)])
    assert r.mark_validated([str(key)], 0, "confirmed/fork-a")
    offline, live = c.snapshot(), c.ready_snapshot(r)
    ctx = CacheReadContext(1, 0, 0)
    bad = CachedAccount(Pubkey.new_unique() if conflict == "owner" else owner,
                        b"" if conflict == "closed" else b"other" if conflict == "data" else b"one", 1, 0)
    with pytest.raises(ValueError, match="Conflicting"): c.update(key, bad)
    for snapshot in (offline, live, c.snapshot()):
        with pytest.raises(ValueError, match="Conflicting"): snapshot.assert_usable()
        with pytest.raises(ValueError, match="Conflicting"): snapshot.get_optional(key, ctx)
    # Revalidating readiness cannot erase ambiguous account bytes in this cache.
    generation = r.begin_recovery("confirmed/fork-b")
    assert r.mark_validated([str(key)], generation, "confirmed/fork-b")
    with pytest.raises(ValueError, match="Conflicting"): c.ready_snapshot(r)
    fresh = SubscriptionAccountCache()
    fresh.update(key, CachedAccount(owner, b"selected", 1, 0))
    assert fresh.ready_snapshot(r).get(key, ctx).data == b"selected"
