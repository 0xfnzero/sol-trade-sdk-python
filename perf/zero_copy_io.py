"""
Zero-copy I/O operations for minimal memory overhead.

Provides buffer pools and serialization that avoid unnecessary
memory copies during transaction building and submission.
"""

import struct
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from collections import deque
import threading
import logging

logger = logging.getLogger(__name__)


@dataclass
class BufferPoolConfig:
    """Configuration for buffer pool."""
    buffer_size: int = 256 * 1024  # 256KB
    pool_size: int = 10000
    enable_auto_grow: bool = False
    max_pool_size: int = 50000


class ZeroCopyBuffer:
    """
    A buffer that supports zero-copy operations.

    Uses memoryview to avoid copying when slicing and dicing.
    """

    def __init__(self, size: int):
        self._buffer = bytearray(size)
        self._view = memoryview(self._buffer)
        self._position = 0
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        """Write data to buffer."""
        with self._lock:
            end = self._position + len(data)
            if end > len(self._buffer):
                raise BufferError("Buffer overflow")

            self._buffer[self._position:end] = data
            self._position = end
            return len(data)

    def write_at(self, offset: int, data: bytes) -> int:
        """Write data at specific offset without changing position."""
        with self._lock:
            end = offset + len(data)
            if end > len(self._buffer):
                raise BufferError("Buffer overflow")

            self._buffer[offset:end] = data
            return len(data)

    def read(self, size: int) -> memoryview:
        """Read data from current position (zero-copy)."""
        with self._lock:
            end = self._position + size
            if end > len(self._buffer):
                raise BufferError("Buffer underflow")

            result = self._view[self._position:end]
            self._position = end
            return result

    def read_at(self, offset: int, size: int) -> memoryview:
        """Read data at specific offset without changing position."""
        end = offset + size
        if end > len(self._buffer):
            raise BufferError("Buffer underflow")
        return self._view[offset:end]

    def get_view(self, start: int = 0, end: Optional[int] = None) -> memoryview:
        """Get a memoryview of the buffer (zero-copy)."""
        return self._view[start:end]

    def seek(self, position: int) -> None:
        """Seek to position."""
        if position < 0 or position > len(self._buffer):
            raise ValueError("Invalid position")
        self._position = position

    def tell(self) -> int:
        """Get current position."""
        return self._position

    def remaining(self) -> int:
        """Get remaining space in buffer."""
        return len(self._buffer) - self._position

    def clear(self) -> None:
        """Clear buffer (just reset position)."""
        self._position = 0

    def __len__(self) -> int:
        return self._position


class BufferPool:
    """
    Pool of pre-allocated buffers for zero-copy operations.

    Reduces allocation overhead in hot paths.
    """

    def __init__(self, config: Optional[BufferPoolConfig] = None):
        self.config = config or BufferPoolConfig()
        self._pool: deque[ZeroCopyBuffer] = deque()
        self._lock = threading.Lock()
        self._allocated = 0
        self._total_allocated = 0

        # Pre-allocate buffers
        for _ in range(self.config.pool_size):
            self._pool.append(self._create_buffer())

    def _create_buffer(self) -> ZeroCopyBuffer:
        """Create a new buffer."""
        self._total_allocated += 1
        return ZeroCopyBuffer(self.config.buffer_size)

    def acquire(self) -> ZeroCopyBuffer:
        """Acquire a buffer from the pool."""
        with self._lock:
            if self._pool:
                self._allocated += 1
                return self._pool.popleft()

            # Pool empty - create new if auto-grow enabled
            if self.config.enable_auto_grow and self._total_allocated < self.config.max_pool_size:
                return self._create_buffer()

        # Fallback: create temporary buffer
        logger.warning("Buffer pool exhausted, creating temporary buffer")
        return ZeroCopyBuffer(self.config.buffer_size)

    def release(self, buffer: ZeroCopyBuffer) -> None:
        """Release buffer back to pool."""
        buffer.clear()

        with self._lock:
            self._allocated -= 1
            # Only return to pool if it's the right size
            if len(buffer._buffer) == self.config.buffer_size:
                self._pool.append(buffer)

    def stats(self) -> Dict[str, int]:
        """Get pool statistics."""
        with self._lock:
            return {
                "available": len(self._pool),
                "allocated": self._allocated,
                "total_allocated": self._total_allocated,
                "pool_size": self.config.pool_size,
            }


class ZeroCopySerializer:
    """
    Serializer that uses zero-copy techniques.

    Writes directly to pre-allocated buffers to avoid
    intermediate allocations.
    """

    def __init__(self, buffer_pool: Optional[BufferPool] = None):
        self.buffer_pool = buffer_pool or BufferPool()
        self._buffer: Optional[ZeroCopyBuffer] = None

    def start(self) -> None:
        """Start serialization with a fresh buffer."""
        if self._buffer:
            self.buffer_pool.release(self._buffer)
        self._buffer = self.buffer_pool.acquire()

    def end(self) -> memoryview:
        """End serialization and return the result."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")

        result = self._buffer.get_view(0, len(self._buffer))
        # Don't release buffer - caller owns it now
        buffer = self._buffer
        self._buffer = None
        return result

    def write_u8(self, value: int) -> None:
        """Write unsigned 8-bit integer."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")
        self._buffer.write(struct.pack('<B', value))

    def write_u16(self, value: int) -> None:
        """Write unsigned 16-bit integer."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")
        self._buffer.write(struct.pack('<H', value))

    def write_u32(self, value: int) -> None:
        """Write unsigned 32-bit integer."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")
        self._buffer.write(struct.pack('<I', value))

    def write_u64(self, value: int) -> None:
        """Write unsigned 64-bit integer."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")
        self._buffer.write(struct.pack('<Q', value))

    def write_bytes(self, data: bytes) -> None:
        """Write raw bytes."""
        if not self._buffer:
            raise RuntimeError("Serialization not started")
        self._buffer.write(data)

    def write_bytes_with_length(self, data: bytes) -> None:
        """Write bytes prefixed with length (u32)."""
        self.write_u32(len(data))
        self.write_bytes(data)

    def release_buffer(self, buffer: ZeroCopyBuffer) -> None:
        """Release a buffer back to the pool."""
        self.buffer_pool.release(buffer)


# Global buffer pool
_global_buffer_pool: Optional[BufferPool] = None


def get_buffer_pool(config: Optional[BufferPoolConfig] = None) -> BufferPool:
    """Get or create global buffer pool."""
    global _global_buffer_pool
    if _global_buffer_pool is None:
        _global_buffer_pool = BufferPool(config)
    return _global_buffer_pool
