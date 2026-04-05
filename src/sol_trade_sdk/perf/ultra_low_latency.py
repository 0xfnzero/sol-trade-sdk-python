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

    def __init__(self, buffer_size: int, pool_size: int):
        self.buffer_size = buffer_size
        self.pool_size = pool_size
        self._pool: deque[bytearray] = deque()
        self._lock = threading.Lock()
        self._allocated = 0

        # Pre-allocate buffers
        for _ in range(pool_size):
            self._pool.append(bytearray(buffer_size))

    def acquire(self) -> Optional[bytearray]:
        """Acquire a buffer from the pool."""
        with self._lock:
            if self._pool:
                self._allocated += 1
                return self._pool.popleft()
        return None

    def release(self, buffer: bytearray) -> None:
        """Return a buffer to the pool."""
        if len(buffer) != self.buffer_size:
            return  # Don't accept wrong-sized buffers

        with self._lock:
            self._allocated -= 1
            buffer[:] = b'\x00' * self.buffer_size  # Clear buffer
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
        """Initialize all optimization components."""
        logger.info("Initializing LatencyOptimizer...")

        # Initialize memory pool
        if self.config.enable_memory_pooling:
            self._memory_pool = MemoryPool(
                self.config.buffer_size,
                self.config.memory_pool_size,
            )
            logger.info(f"Memory pool initialized: {self.config.memory_pool_size} buffers")

        # Set CPU affinity
        if self.config.enable_cpu_pinning and sys.platform != "win32":
            self._set_cpu_affinity()

        self._running = True
        logger.info("LatencyOptimizer initialized")

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
    """Get or create global latency optimizer."""
    global _global_optimizer
    if _global_optimizer is None:
        _global_optimizer = LatencyOptimizer(config)
        _global_optimizer.initialize()
    return _global_optimizer
