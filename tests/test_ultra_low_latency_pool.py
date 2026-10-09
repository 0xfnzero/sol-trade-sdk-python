import pytest

from src.perf import ultra_low_latency as ull


def test_global_helper_default_initialization_is_bounded_and_ready(monkeypatch):
    monkeypatch.setattr(ull, "_global_optimizer", None)
    monkeypatch.setattr(ull.LatencyOptimizer, "_set_cpu_affinity", lambda self: None)
    optimizer = ull.get_latency_optimizer()
    assert optimizer._memory_pool.pool_size == 64
    assert optimizer.acquire_buffer() is not None
    assert ull.get_latency_optimizer() is optimizer


def test_default_optimizer_prewarm_is_budgeted_and_acquire_does_not_allocate(monkeypatch):
    config = ull.UltraLowLatencyConfig(enable_cpu_pinning=False)
    optimizer = ull.LatencyOptimizer(config)
    optimizer.initialize()
    pool = optimizer._memory_pool
    assert config.memory_pool_size == 10000  # Existing requested-capacity configuration retained.
    assert pool.pool_size == 64
    assert pool.pool_size * pool.buffer_size == config.memory_pool_budget_bytes
    def unexpected_allocation(*args):
        raise AssertionError("allocation on buffer acquisition")
    monkeypatch.setattr(ull, "bytearray", unexpected_allocation, raising=False)
    buffers = [optimizer.acquire_buffer() for _ in range(64)]
    assert all(buffer is not None and len(buffer) == 256 * 1024 for buffer in buffers)
    assert optimizer.acquire_buffer() is None
    for buffer in buffers:
        optimizer.release_buffer(buffer)
    assert pool.utilization() == 0


def test_explicit_lazy_prewarm_is_bounded_and_does_not_refill_live_leases():
    config = ull.UltraLowLatencyConfig(memory_pool_size=10000, buffer_size=8,
                                       enable_cpu_pinning=False, memory_pool_budget_bytes=32,
                                       prewarm_memory_pool=False)
    optimizer = ull.LatencyOptimizer(config)
    optimizer.initialize()
    assert optimizer.acquire_buffer() is None
    optimizer.prewarm_buffers(2)
    first, second = optimizer.acquire_buffer(), optimizer.acquire_buffer()
    assert first is not None and second is not None
    optimizer.prewarm_buffers(2)
    assert optimizer.acquire_buffer() is None
    optimizer.prewarm_buffers()
    remaining = [optimizer.acquire_buffer(), optimizer.acquire_buffer()]
    assert all(buffer is not None for buffer in remaining)
    assert optimizer.acquire_buffer() is None
    for buffer in [first, second] + remaining:
        optimizer.release_buffer(buffer)
    assert optimizer._memory_pool.utilization() == 0


def test_direct_constructor_remains_prewarmed_and_clear_template_uses_budget():
    pool = ull.MemoryPool(8, 10000, clear_on_release=True, memory_budget_bytes=32)
    assert pool.pool_size == 3
    assert pool.pool_size * pool.buffer_size + len(pool._zero_buffer) == 32
    buffer = pool.acquire()
    buffer[:] = bytes([255]) * 8
    pool.release(buffer)
    assert buffer == bytes(8)


@pytest.mark.parametrize("name,value", [("buffer_size", 0), ("buffer_size", -1), ("buffer_size", True),
                                        ("buffer_size", 1.5), ("pool_size", 0), ("pool_size", -1),
                                        ("pool_size", True), ("memory_budget_bytes", 0),
                                        ("memory_budget_bytes", -1), ("memory_budget_bytes", True),
                                        ("memory_budget_bytes", 1.5)])
def test_pool_rejects_invalid_sizes_and_budgets(name, value):
    args = dict(buffer_size=8, pool_size=4, memory_budget_bytes=32)
    args[name] = value
    with pytest.raises(ValueError):
        ull.MemoryPool(**args)


def test_pool_rejects_buffer_or_template_that_cannot_fit():
    with pytest.raises(ValueError): ull.MemoryPool(64, 4, memory_budget_bytes=32)
    with pytest.raises(ValueError): ull.MemoryPool(32, 4, clear_on_release=True, memory_budget_bytes=32)
    with pytest.raises(ValueError): ull.UltraLowLatencyConfig(memory_pool_budget_bytes=0)
    with pytest.raises(ValueError): ull.UltraLowLatencyConfig(prewarm_memory_pool=1)


@pytest.mark.parametrize("count", [-1, True, 1.5, 5])
def test_prewarm_rejects_invalid_target(count):
    pool = ull.MemoryPool(8, 4, memory_budget_bytes=32, prewarm=False)
    with pytest.raises(ValueError): pool.prewarm(count)
    assert pool.acquire() is None


def test_disabled_pool_cannot_be_prewarmed():
    optimizer = ull.LatencyOptimizer(ull.UltraLowLatencyConfig(enable_memory_pooling=False, enable_cpu_pinning=False))
    optimizer.initialize()
    assert optimizer.acquire_buffer() is None
    with pytest.raises(RuntimeError): optimizer.prewarm_buffers()


def test_foreign_and_double_release_never_create_aliasing_leases():
    pool = ull.MemoryPool(8, 2, memory_budget_bytes=16)
    first, second = pool.acquire(), pool.acquire()
    pool.release(bytearray(8))
    assert pool.acquire() is None and pool.utilization() == 100
    pool.release(first)
    pool.release(first)
    borrowed = pool.acquire()
    assert borrowed is first
    assert pool.acquire() is None
    borrowed[0] = 42
    assert second[0] == 0
    pool.release(borrowed)
    pool.release(second)
    assert pool.utilization() == 0
