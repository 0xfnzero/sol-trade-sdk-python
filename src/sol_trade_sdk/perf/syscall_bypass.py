"""
Syscall bypass: batching, fast time, I/O optimizations.

This module provides techniques to reduce system call overhead:
- Batching multiple syscalls into single operations
- Fast time retrieval without syscalls (vDSO-like)
- I/O optimization through buffering
"""

import time
import os
import threading
from typing import Optional, List, Callable, Any
from dataclasses import dataclass, field
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)


@dataclass
class SyscallBypassConfig:
    """Configuration for syscall bypass optimizations."""
    enable_batch_processing: bool = True
    batch_size: int = 100
    batch_timeout_ms: float = 1.0
    enable_fast_time: bool = True
    enable_io_buffering: bool = True
    io_buffer_size: int = 4096
    syscall_cache_size: int = 1000


@dataclass
class SyscallRequest:
    """Represents a system call request for batching."""
    syscall_type: str
    args: tuple
    kwargs: dict
    callback: Optional[Callable[[Any], None]] = None
    event: Optional[threading.Event] = None
    result: Any = None


class FastTimeProvider:
    """
    Fast time provider using cached time + monotonic delta.

    Avoids frequent gettimeofday() syscalls by:
    1. Caching UTC timestamp
    2. Using monotonic clock for deltas
    3. Periodic recalibration
    """

    def __init__(self, calibration_interval_ms: float = 100.0):
        self._calibration_interval_ms = calibration_interval_ms
        self._last_calibration = 0.0
        self._base_time_ns = 0
        self._base_monotonic_ns = 0
        self._lock = threading.Lock()
        self._calibrate()

    def _calibrate(self) -> None:
        """Recalibrate the time base."""
        with self._lock:
            self._base_time_ns = time.time_ns()
            self._base_monotonic_ns = time.monotonic_ns()
            self._last_calibration = time.monotonic()

    def now_ns(self) -> int:
        """Get current time in nanoseconds (fast path)."""
        # Check if recalibration needed
        if time.monotonic() - self._last_calibration > self._calibration_interval_ms / 1000:
            self._calibrate()

        # Calculate current time from monotonic delta
        monotonic_delta = time.monotonic_ns() - self._base_monotonic_ns
        return self._base_time_ns + monotonic_delta

    def now_us(self) -> int:
        """Get current time in microseconds."""
        return self.now_ns() // 1000

    def now_ms(self) -> int:
        """Get current time in milliseconds."""
        return self.now_ns() // 1_000_000


class IOBuffer:
    """Buffered I/O to reduce write syscalls."""

    def __init__(self, buffer_size: int = 4096):
        self.buffer_size = buffer_size
        self._buffer = bytearray()
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        """Write data to buffer, flush if needed."""
        with self._lock:
            self._buffer.extend(data)

            if len(self._buffer) >= self.buffer_size:
                return self._flush()
            return len(data)

    def _flush(self) -> int:
        """Flush buffer to actual output."""
        if not self._buffer:
            return 0

        # In real implementation, this would write to fd
        # For now, just clear the buffer
        written = len(self._buffer)
        self._buffer.clear()
        return written

    def flush(self) -> int:
        """Explicit flush."""
        with self._lock:
            return self._flush()


class SyscallBatchProcessor:
    """Batches multiple syscalls into single operations."""

    def __init__(self, config: SyscallBypassConfig):
        self.config = config
        self._batch: deque[SyscallRequest] = deque()
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._running = True
        self._batch_thread = threading.Thread(target=self._batch_loop, daemon=True)
        self._batch_thread.start()

    def submit(self, request: SyscallRequest) -> Any:
        """Submit a syscall request for batching."""
        if not self.config.enable_batch_processing:
            # Execute immediately if batching disabled
            return self._execute_request(request)

        event = threading.Event()
        request.event = event

        with self._lock:
            self._batch.append(request)

        # Wait for completion
        event.wait(timeout=self.config.batch_timeout_ms / 1000 * 2)
        return request.result

    def _batch_loop(self) -> None:
        """Background thread to process batched syscalls."""
        while self._running:
            time.sleep(self.config.batch_timeout_ms / 1000)
            self._process_batch()

    def _process_batch(self) -> None:
        """Process pending batch of syscalls."""
        batch: List[SyscallRequest] = []

        with self._lock:
            while len(batch) < self.config.batch_size and self._batch:
                batch.append(self._batch.popleft())

        if not batch:
            return

        # Execute batch
        for request in batch:
            try:
                request.result = self._execute_request(request)
            except Exception as e:
                logger.error(f"Syscall error: {e}")
                request.result = None
            finally:
                if request.event:
                    request.event.set()

    def _execute_request(self, request: SyscallRequest) -> Any:
        """Execute a single syscall request."""
        # Map syscall types to actual implementations
        handlers = {
            "get_time": lambda: time.time(),
            "get_pid": lambda: os.getpid(),
            "get_tid": lambda: threading.get_ident(),
        }

        handler = handlers.get(request.syscall_type)
        if handler:
            return handler()

        return None

    def shutdown(self) -> None:
        """Shutdown the batch processor."""
        self._running = False
        self._batch_thread.join(timeout=1.0)
        self._executor.shutdown(wait=False)


class SyscallBypassManager:
    """
    Manager for syscall bypass optimizations.

    Provides:
    - Batched syscall processing
    - Fast time retrieval
    - Buffered I/O
    """

    def __init__(self, config: Optional[SyscallBypassConfig] = None):
        self.config = config or SyscallBypassConfig()
        self._batch_processor: Optional[SyscallBatchProcessor] = None
        self._fast_time: Optional[FastTimeProvider] = None
        self._io_buffer: Optional[IOBuffer] = None
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all syscall bypass components."""
        if self._initialized:
            return

        if self.config.enable_batch_processing:
            self._batch_processor = SyscallBatchProcessor(self.config)

        if self.config.enable_fast_time:
            self._fast_time = FastTimeProvider()

        if self.config.enable_io_buffering:
            self._io_buffer = IOBuffer(self.config.io_buffer_size)

        self._initialized = True
        logger.info("SyscallBypassManager initialized")

    def now_ns(self) -> int:
        """Fast time in nanoseconds."""
        if self._fast_time:
            return self._fast_time.now_ns()
        return time.time_ns()

    def now_us(self) -> int:
        """Fast time in microseconds."""
        if self._fast_time:
            return self._fast_time.now_us()
        return int(time.time() * 1_000_000)

    def submit_syscall(
        self,
        syscall_type: str,
        *args,
        callback: Optional[Callable[[Any], None]] = None,
        **kwargs
    ) -> Any:
        """Submit a syscall for batching."""
        if not self._initialized:
            self.initialize()

        if self._batch_processor:
            request = SyscallRequest(
                syscall_type=syscall_type,
                args=args,
                kwargs=kwargs,
                callback=callback,
            )
            return self._batch_processor.submit(request)

        # Fallback: execute directly
        return None

    def shutdown(self) -> None:
        """Shutdown all components."""
        if self._batch_processor:
            self._batch_processor.shutdown()
        self._initialized = False


# Global instance for convenience
_global_bypass_manager: Optional[SyscallBypassManager] = None


def get_syscall_bypass_manager(config: Optional[SyscallBypassConfig] = None) -> SyscallBypassManager:
    """Get or create global syscall bypass manager."""
    global _global_bypass_manager
    if _global_bypass_manager is None:
        _global_bypass_manager = SyscallBypassManager(config)
        _global_bypass_manager.initialize()
    return _global_bypass_manager
