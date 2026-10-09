import pytest
from src.hotpath.state import AccountState, PoolState, PrefetchedData

@pytest.mark.parametrize('kind', ['blockhash', 'account', 'pool'])
def test_manual_cache_objects_never_resurrect_after_wall_clock_rollback(kind, monkeypatch):
    clock = {'wall': 1000.0, 'mono': 50.0}
    monkeypatch.setattr('src.hotpath.state.time.time', lambda: clock['wall'])
    monkeypatch.setattr('src.hotpath.state.time.monotonic', lambda: clock['mono'])
    if kind == 'blockhash': data = PrefetchedData(blockhash='cached', fetched_at=999.5)
    elif kind == 'account': data = AccountState('key', b'', 1, 'owner', False, 0, 0, fetched_at=999.5)
    else: data = PoolState('pool', 'dex', 'a', 'b', 'va', 'vb', 1, 1, 0, fetched_at=999.5)
    assert data.is_fresh(1.0)
    clock.update(wall=5000.0, mono=50.5)
    assert data.is_fresh(1.0)  # Inclusive TTL; wall jumps are diagnostics only.
    clock.update(wall=1000.0, mono=50.500001)
    assert not data.is_fresh(1.0)
    clock.update(wall=999.75, mono=51.0)
    assert not data.is_fresh(1.0)

@pytest.mark.parametrize('kind', ['blockhash', 'account', 'pool'])
def test_manual_cache_preserves_initial_age_instead_of_refreshing_old_data(kind, monkeypatch):
    monkeypatch.setattr('src.hotpath.state.time.time', lambda: 1000.0)
    monkeypatch.setattr('src.hotpath.state.time.monotonic', lambda: 50.0)
    if kind == 'blockhash': data = PrefetchedData(blockhash='cached', fetched_at=998.0)
    elif kind == 'account': data = AccountState('key', b'', 1, 'owner', False, 0, 0, fetched_at=998.0)
    else: data = PoolState('pool', 'dex', 'a', 'b', 'va', 'vb', 1, 1, 0, fetched_at=998.0)
    assert not data.is_fresh(1.0)
