"""
Ultra-low latency optimizations for high-frequency trading.

This module provides end-to-end latency optimizations:
- Memory pre-allocation and pooling
- Lock-free data structures
- CPU cache optimization
- Branch prediction hints
"""

import os
import sys
import time
import threading
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)

DEFAULT_MEMORY_POOL_BUDGET_BYTES = 16 * 1024 * 1024


def _pool_capacity(buffer_size, pool_size, memory_budget_bytes, clear_on_release=False):
    for name, value in (("buffer_size", buffer_size), ("pool_size", pool_size),
                        ("memory_budget_bytes", memory_budget_bytes)):
        if type(value) is not int or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    # The zeroing template is part of the same buffer-byte budget. Python
    # object/lock/deque overhead is additional and bounded by this capacity.
    available = memory_budget_bytes - (buffer_size if clear_on_release else 0)
    capacity = min(pool_size, available // buffer_size)
    if capacity < 1:
        raise ValueError("Memory pool budget must fit a buffer and its zeroing template")
    return capacity


@dataclass
class UltraLowLatencyConfig:
    """Configuration for ultra-low latency mode."""
    # Memory
    enable_memory_pooling: bool = True
    memory_pool_size: int = 10000
    buffer_size: int = 256 * 1024  # 256KB buffers

    # CPU
    enable_cpu_pinning: bool = True
    cpu_cores: Optional[List[int]] = None

    # Prefetch
    enable_prefetch: bool = True
    prefetch_distance: int = 4

    # Threading
    worker_threads: int = 4
    use_isolated_workers: bool = True

    # Latency targets
    target_latency_us: int = 100  # 100 microseconds

    # Appended to preserve existing positional configuration arguments.
    # Total buffer payload budget, including any zeroing template; object
    # overhead is additional. Requested memory_pool_size is an upper bound.
    memory_pool_budget_bytes: int = DEFAULT_MEMORY_POOL_BUDGET_BYTES
    prewarm_memory_pool: bool = True

    def __post_init__(self):
        _pool_capacity(self.buffer_size, self.memory_pool_size, self.memory_pool_budget_bytes)
        if type(self.prewarm_memory_pool) is not bool:
            raise ValueError("prewarm_memory_pool must be boolean")


@dataclass
class LatencyMetrics:
    """Metrics for latency tracking."""
    min_latency_us: int = 0
    max_latency_us: int = 0
    avg_latency_us: float = 0.0
    p50_latency_us: int = 0
    p99_latency_us: int = 0
    p999_latency_us: int = 0
    total_operations: int = 0


class MemoryPool:
    """
    Pre-allocated memory pool to avoid malloc overhead.

    Provides fixed-size buffers for zero-allocation hot paths.
    """

    def __init__(self, buffer_size: int, pool_size: int, clear_on_release: bool = False,
                 *, memory_budget_bytes: int = DEFAULT_MEMORY_POOL_BUDGET_BYTES,
                 prewarm: bool = True):
        if type(clear_on_release) is not bool or type(prewarm) is not bool:
            raise ValueError("clear_on_release and prewarm must be boolean")
        self.buffer_size = buffer_size
        self.requested_pool_size = pool_size
        self.pool_size = _pool_capacity(buffer_size, pool_size, memory_budget_bytes, clear_on_release)
        self.memory_budget_bytes = memory_budget_bytes
        self.clear_on_release = clear_on_release
        self._pool: deque[bytearray] = deque()
        self._lock = threading.Lock()
        self._allocated = 0
        self._warmed = 0
        self._leased = {}  # Preallocated identity slots; foreign/double returns never enter the pool.
        self._zero_buffer = None

        if prewarm:
            self.prewarm()

    def prewarm(self, count: Optional[int] = None) -> None:
        """Cold path: allocate up to a target number of buffers within the budget.

        Count includes checked-out buffers; repeated calls do not refill those
        leases. acquire() never allocates, including an exhausted or lazy pool.
        """
        target = self.pool_size if count is None else count
        if type(target) is not int or not 0 <= target <= self.pool_size:
            raise ValueError("Prewarm count must be an integer within pool capacity")
        with self._lock:
            if target > self._warmed and self.clear_on_release and self._zero_buffer is None:
                self._zero_buffer = bytes(self.buffer_size)
            while self._warmed < target:
                buffer = bytearray(self.buffer_size)
                self._pool.append(buffer)
                self._leased[id(buffer)] = [buffer, False]
                self._warmed += 1

    def acquire(self) -> Optional[bytearray]:
        """Acquire a buffer from the pool."""
        with self._lock:
            if self._pool:
                buffer = self._pool.popleft()
                self._leased[id(buffer)][1] = True
                self._allocated += 1
                return buffer
        return None

    def release(self, buffer: bytearray) -> None:
        """Return a buffer to the pool."""
        if len(buffer) != self.buffer_size:
            return  # Don't accept wrong-sized buffers

        with self._lock:
            lease = self._leased.get(id(buffer))
            if lease is None or lease[0] is not buffer or not lease[1]:
                return
            lease[1] = False
            self._allocated -= 1
            if self._zero_buffer is not None:
                buffer[:] = self._zero_buffer
            self._pool.append(buffer)

    def utilization(self) -> float:
        """Get pool utilization percentage."""
        with self._lock:
            return self._allocated / self.pool_size * 100


class LockFreeQueue:
    """
    Simple lock-free queue using atomic operations.

    Note: Python's GIL limits true lock-freedom, but this
    minimizes lock contention compared to standard queue.
    """

    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._queue: deque[Any] = deque(maxlen=maxsize)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)

    def put(self, item: Any, block: bool = True, timeout: Optional[float] = None) -> bool:
        """Put item into queue."""
        with self._lock:
            if len(self._queue) >= self.maxsize:
                if not block:
                    return False
                if not self._not_full.wait(timeout=timeout):
                    return False

            self._queue.append(item)
            self._not_empty.notify()
            return True

    def get(self, block: bool = True, timeout: Optional[float] = None) -> Any:
        """Get item from queue."""
        with self._lock:
            if not self._queue:
                if not block:
                    raise Exception("Queue empty")
                if not self._not_empty.wait(timeout=timeout):
                    raise Exception("Timeout")

            item = self._queue.popleft()
            self._not_full.notify()
            return item

    def qsize(self) -> int:
        """Get queue size."""
        with self._lock:
            return len(self._queue)


class CacheOptimizer:
    """
    CPU cache optimization utilities.

    Provides cache-line alignment and prefetch hints.
    """

    CACHE_LINE_SIZE = 64  # bytes

    @staticmethod
    def align_to_cache_line(size: int) -> int:
        """Round up size to cache line boundary."""
        return (size + CacheOptimizer.CACHE_LINE_SIZE - 1) // CacheOptimizer.CACHE_LINE_SIZE * CacheOptimizer.CACHE_LINE_SIZE

    @staticmethod
    def prefetch_read(address: int) -> None:
        """
        Prefetch data for reading.

        Note: In Python, this is a hint only. True prefetch
        requires C extensions or ctypes.
        """
        # Placeholder for prefetch hint
        pass

    @staticmethod
    def prefetch_write(address: int) -> None:
        """Prefetch data for writing."""
        pass


class LatencyOptimizer:
    """
    Main optimizer for ultra-low latency trading.

    Coordinates all latency optimizations:
    - Memory pooling
    - CPU affinity
    - Prefetching
    - Worker isolation
    """

    def __init__(self, config: Optional[UltraLowLatencyConfig] = None):
        self.config = config or UltraLowLatencyConfig()
        self._memory_pool: Optional[MemoryPool] = None
        self._workers: List[threading.Thread] = []
        self._running = False
        self._metrics = LatencyMetrics()
        self._latency_history: deque[int] = deque(maxlen=10000)

    def initialize(self) -> None:
        """Cold path: initialize bounded pools before latency-sensitive calls.

        Default prewarming retains acquire-after-initialize compatibility. Set
        prewarm_memory_pool=False and call prewarm_buffers() explicitly to defer.
        """
        logger.info("Initializing LatencyOptimizer...")

        # Initialize memory pool
        if self.config.enable_memory_pooling:
            self._memory_pool = MemoryPool(
                self.config.buffer_size,
                self.config.memory_pool_size,
                memory_budget_bytes=self.config.memory_pool_budget_bytes,
                prewarm=self.config.prewarm_memory_pool,
            )
            logger.info("Memory pool capacity: %s buffers (requested %s)",
                        self._memory_pool.pool_size, self.config.memory_pool_size)

        # Set CPU affinity
        if self.config.enable_cpu_pinning and sys.platform != "win32":
            self._set_cpu_affinity()

        self._running = True
        logger.info("LatencyOptimizer initialized")

    def prewarm_buffers(self, count: Optional[int] = None) -> None:
        """Allocate pooled buffers during cold initialization, never on acquire."""
        if self._memory_pool is None:
            raise RuntimeError("Initialize an enabled memory pool before prewarming")
        self._memory_pool.prewarm(count)

    def _set_cpu_affinity(self) -> None:
        """Set CPU affinity for current process."""
        try:
            import psutil

            cores = self.config.cpu_cores or list(range(os.cpu_count() or 4))
            process = psutil.Process()
            process.cpu_affinity(cores)
            logger.info(f"CPU affinity set to cores: {cores}")
        except Exception as e:
            logger.warning(f"Failed to set CPU affinity: {e}")

    def acquire_buffer(self) -> Optional[bytearray]:
        """Acquire a pre-allocated buffer."""
        if self._memory_pool:
            return self._memory_pool.acquire()
        return None

    def release_buffer(self, buffer: bytearray) -> None:
        """Release buffer back to pool."""
        if self._memory_pool:
            self._memory_pool.release(buffer)

    def record_latency(self, latency_us: int) -> None:
        """Record a latency measurement."""
        self._latency_history.append(latency_us)

        # Update metrics periodically
        if len(self._latency_history) >= 100:
            self._update_metrics()

    def _update_metrics(self) -> None:
        """Update latency metrics from history."""
        if not self._latency_history:
            return

        sorted_latencies = sorted(self._latency_history)
        n = len(sorted_latencies)

        self._metrics.min_latency_us = sorted_latencies[0]
        self._metrics.max_latency_us = sorted_latencies[-1]
        self._metrics.avg_latency_us = sum(sorted_latencies) / n
        self._metrics.p50_latency_us = sorted_latencies[n // 2]
        self._metrics.p99_latency_us = sorted_latencies[int(n * 0.99)]
        self._metrics.p999_latency_us = sorted_latencies[int(n * 0.999)]
        self._metrics.total_operations += n

        self._latency_history.clear()

    def get_metrics(self) -> LatencyMetrics:
        """Get current latency metrics."""
        return self._metrics

    def likely(self, condition: bool) -> bool:
        """
        Branch prediction hint - likely to be true.

        In Python this is a no-op, but documents intent.
        """
        return condition

    def unlikely(self, condition: bool) -> bool:
        """
        Branch prediction hint - unlikely to be true.

        In Python this is a no-op, but documents intent.
        """
        return condition

    def shutdown(self) -> None:
        """Shutdown the optimizer."""
        self._running = False
        logger.info("LatencyOptimizer shutdown")


# Convenience functions
def likely(condition: bool) -> bool:
    """Branch prediction hint - likely true."""
    return condition


def unlikely(condition: bool) -> bool:
    """Branch prediction hint - unlikely true."""
    return condition


# Global optimizer instance
_global_optimizer: Optional[LatencyOptimizer] = None


def get_latency_optimizer(config: Optional[UltraLowLatencyConfig] = None) -> LatencyOptimizer:
    """Get or create the optimizer; call once during cold initialization.

    First creation prewarms at most the configured buffer-byte budget (16 MiB
    by default), not all 10,000 requested slots. Buffer acquisition is allocation-free.
    """
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = LatencyOptimizer(config)
        _global_optimizer.initialize()
    return _global_optimizer
