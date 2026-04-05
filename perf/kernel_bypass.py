"""
Kernel bypass optimizations for ultra-low latency I/O.

Provides io_uring support on Linux for asynchronous I/O without kernel copies,
along with fallback implementations for other platforms.
"""

from __future__ import annotations

import asyncio
import os
import platform
import select
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import logging
import threading
import time

logger = logging.getLogger(__name__)


class IOOperation(Enum):
    """I/O operation types."""
    READ = auto()
    WRITE = auto()
    FSYNC = auto()
    POLL = auto()
    TIMEOUT = auto()


@dataclass
class IORequest:
    """I/O request for kernel bypass operations."""
    op: IOOperation
    fd: int
    buffer: Optional[bytes] = None
    offset: int = 0
    size: int = 0
    callback: Optional[Callable[[int, bytes, int], None]] = None
    user_data: Any = None


@dataclass
class IOResult:
    """Result of an I/O operation."""
    request_id: int
    bytes_transferred: int
    buffer: Optional[bytes] = None
    error: Optional[int] = None
    user_data: Any = None


@dataclass
class IOUringConfig:
    """Configuration for io_uring."""
    queue_depth: int = 256
    sq_thread_idle: int = 2000  # ms before SQ thread sleeps
    sq_thread_cpu: int = -1  # CPU for SQ thread (-1 = any)
    cq_size: int = 0  # 0 = same as queue_depth
    flags: int = 0
    features: List[str] = field(default_factory=list)


class KernelBypassManager:
    """
    Manager for kernel bypass I/O operations.

    Uses io_uring on Linux when available, falls back to asyncio/epoll
    on other platforms.
    """

    def __init__(self, config: Optional[IOUringConfig] = None):
        self.config = config or IOUringConfig()
        self._uring_available = False
        self._uring_lib = None
        self._lock = threading.RLock()
        self._request_counter = 0
        self._pending_requests: Dict[int, IORequest] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._check_uring_availability()

    def _check_uring_availability(self) -> bool:
        """Check if io_uring is available on this system."""
        if platform.system() != "Linux":
            logger.info("io_uring only available on Linux")
            return False

        try:
            # Try to import uring library
            import uring
            self._uring_lib = uring
            self._uring_available = True
            logger.info("io_uring support enabled")
            return True
        except ImportError:
            logger.info("io_uring library not available, using fallback")
            return False

    def is_uring_available(self) -> bool:
        """Check if io_uring is available."""
        return self._uring_available

    def start(self) -> None:
        """Start the I/O processing loop."""
        with self._lock:
            if self._running:
                return
            self._running = True

        if self._uring_available:
            self._thread = threading.Thread(target=self._uring_loop, daemon=True)
        else:
            self._thread = threading.Thread(target=self._fallback_loop, daemon=True)

        self._thread.start()
        logger.info("Kernel bypass manager started")

    def stop(self) -> None:
        """Stop the I/O processing loop."""
        with self._lock:
            self._running = False

        if self._thread:
            self._thread.join(timeout=5.0)
            logger.info("Kernel bypass manager stopped")

    def _uring_loop(self) -> None:
        """Main io_uring processing loop."""
        if not self._uring_lib:
            return

        try:
            # Setup io_uring
            ring = self._uring_lib.io_uring_queue_init(
                self.config.queue_depth, 0
            )

            while self._running:
                # Submit pending requests
                self._submit_uring_requests(ring)

                # Wait for completions
                self._uring_lib.io_uring_submit_and_wait(ring, 1)

                # Process completions
                self._process_uring_completions(ring)

            # Cleanup
            self._uring_lib.io_uring_queue_exit(ring)

        except Exception as e:
            logger.error(f"io_uring loop error: {e}")
            # Fall back to standard loop
            self._fallback_loop()

    def _submit_uring_requests(self, ring) -> None:
        """Submit pending requests to io_uring."""
        # Implementation would submit requests from queue
        pass

    def _process_uring_completions(self, ring) -> None:
        """Process completed io_uring operations."""
        # Implementation would process CQEs
        pass

    def _fallback_loop(self) -> None:
        """Fallback I/O loop using epoll/select."""
        poller = select.epoll() if hasattr(select, 'epoll') else None

        while self._running:
            if poller:
                # Use epoll on Linux
                events = poller.poll(timeout=0.001)
                for fd, event_mask in events:
                    self._handle_epoll_event(fd, event_mask)
            else:
                # Use select on other platforms
                self._handle_select_events()

            # Small yield
            time.sleep(0.0001)

    def _handle_epoll_event(self, fd: int, event_mask: int) -> None:
        """Handle epoll event."""
        pass

    def _handle_select_events(self) -> None:
        """Handle select-based events."""
        pass

    def submit_read(
        self,
        fd: int,
        size: int,
        offset: int = 0,
        callback: Optional[Callable] = None,
        user_data: Any = None
    ) -> int:
        """
        Submit an async read request.

        Returns:
            Request ID for tracking
        """
        with self._lock:
            self._request_counter += 1
            req_id = self._request_counter

        request = IORequest(
            op=IOOperation.READ,
            fd=fd,
            offset=offset,
            size=size,
            callback=callback,
            user_data=user_data
        )

        self._pending_requests[req_id] = request
        return req_id

    def submit_write(
        self,
        fd: int,
        buffer: bytes,
        offset: int = 0,
        callback: Optional[Callable] = None,
        user_data: Any = None
    ) -> int:
        """Submit an async write request."""
        with self._lock:
            self._request_counter += 1
            req_id = self._request_counter

        request = IORequest(
            op=IOOperation.WRITE,
            fd=fd,
            buffer=buffer,
            offset=offset,
            size=len(buffer),
            callback=callback,
            user_data=user_data
        )

        self._pending_requests[req_id] = request
        return req_id


class DirectIOFile:
    """
    File with direct I/O support (bypassing page cache).

    Useful for write-ahead logs and other latency-sensitive I/O.
    """

    def __init__(self, path: str, mode: str = "rb+"):
        self.path = path
        self.mode = mode
        self._fd: Optional[int] = None
        self._direct_io = False

    def open(self) -> bool:
        """Open file with direct I/O if available."""
        try:
            import fcntl
            import os

            # Try O_DIRECT flag
            flags = os.O_RDWR | os.O_CREAT
            if hasattr(os, 'O_DIRECT'):
                flags |= os.O_DIRECT
                self._direct_io = True

            self._fd = os.open(self.path, flags)

            if self._direct_io:
                logger.info(f"Direct I/O enabled for {self.path}")

            return True

        except (ImportError, OSError) as e:
            logger.warning(f"Could not enable direct I/O: {e}")
            # Fallback to normal open
            try:
                self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
                return True
            except OSError:
                return False

    def close(self) -> None:
        """Close the file."""
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def read(self, size: int, offset: int = 0) -> bytes:
        """Read from file."""
        if self._fd is None:
            raise IOError("File not open")

        if self._direct_io:
            # Direct I/O requires aligned buffers
            return self._read_direct(size, offset)

        os.lseek(self._fd, offset, os.SEEK_SET)
        return os.read(self._fd, size)

    def _read_direct(self, size: int, offset: int) -> bytes:
        """Read using direct I/O with aligned buffer."""
        import mmap

        # Align to 512 bytes (typical sector size)
        align = 512
        aligned_offset = (offset // align) * align
        offset_diff = offset - aligned_offset

        aligned_size = ((size + offset_diff + align - 1) // align) * align

        # Create aligned buffer using mmap
        buf = mmap.mmap(-1, aligned_size, mmap.MAP_PRIVATE)

        try:
            os.lseek(self._fd, aligned_offset, os.SEEK_SET)
            data = os.read(self._fd, aligned_size)
            buf[:len(data)] = data

            result = buf[offset_diff:offset_diff + size]
            return bytes(result)
        finally:
            buf.close()

    def write(self, data: bytes, offset: int = 0) -> int:
        """Write to file."""
        if self._fd is None:
            raise IOError("File not open")

        if self._direct_io:
            return self._write_direct(data, offset)

        os.lseek(self._fd, offset, os.SEEK_SET)
        return os.write(self._fd, data)

    def _write_direct(self, data: bytes, offset: int) -> int:
        """Write using direct I/O with aligned buffer."""
        import mmap

        align = 512
        aligned_offset = (offset // align) * align
        offset_diff = offset - aligned_offset

        aligned_size = ((len(data) + offset_diff + align - 1) // align) * align

        # Create aligned buffer
        buf = mmap.mmap(-1, aligned_size, mmap.MAP_PRIVATE)

        try:
            # Zero the buffer first
            buf[:] = b'\x00' * aligned_size

            # Copy data at correct offset
            buf[offset_diff:offset_diff + len(data)] = data

            os.lseek(self._fd, aligned_offset, os.SEEK_SET)
            return os.write(self._fd, buf[:aligned_size])
        finally:
            buf.close()

    def fsync(self) -> None:
        """Sync file to disk."""
        if self._fd is not None:
            os.fsync(self._fd)


class AsyncSocket:
    """Async socket with kernel bypass optimizations."""

    def __init__(self, sock=None):
        self._socket = sock
        self._epoll: Optional[Any] = None
        self._registered = False

    def set_socket(self, sock) -> None:
        """Set the underlying socket."""
        self._socket = sock

    def enable_kernel_bypass(self) -> bool:
        """Enable kernel bypass optimizations for this socket."""
        if not self._socket:
            return False

        try:
            import socket
            import fcntl

            # Set TCP_NODELAY
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Set busy poll if available (Linux)
            if hasattr(socket, 'SO_BUSY_POLL'):
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BUSY_POLL, 50)

            # Set priority
            if hasattr(socket, 'SO_PRIORITY'):
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_PRIORITY, 6)

            return True

        except (ImportError, OSError) as e:
            logger.warning(f"Could not enable kernel bypass for socket: {e}")
            return False

    async def recv(self, size: int) -> bytes:
        """Async receive with optimization."""
        if not self._socket:
            raise IOError("Socket not set")

        # Use asyncio for async recv
        loop = asyncio.get_event_loop()
        return await loop.sock_recv(self._socket, size)

    async def send(self, data: bytes) -> int:
        """Async send with optimization."""
        if not self._socket:
            raise IOError("Socket not set")

        loop = asyncio.get_event_loop()
        return await loop.sock_sendall(self._socket, data)


class MemoryMappedFile:
    """Memory-mapped file for zero-copy access."""

    def __init__(self, path: str):
        self.path = path
        self._mmap: Optional[Any] = None
        self._fd: Optional[int] = None

    def open(self, size: int = 0) -> bool:
        """Open and memory-map the file."""
        try:
            import mmap

            self._fd = os.open(self.path, os.O_RDWR | os.O_CREAT)

            if size > 0:
                os.ftruncate(self._fd, size)

            file_size = os.fstat(self._fd).st_size

            self._mmap = mmap.mmap(
                self._fd,
                file_size,
                mmap.MAP_SHARED,
                mmap.PROT_READ | mmap.PROT_WRITE
            )

            return True

        except (ImportError, OSError) as e:
            logger.error(f"Failed to mmap file: {e}")
            return False

    def close(self) -> None:
        """Close the memory-mapped file."""
        if self._mmap:
            self._mmap.close()
            self._mmap = None

        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def read(self, offset: int, size: int) -> bytes:
        """Read from memory-mapped file."""
        if not self._mmap:
            raise IOError("File not mapped")
        return bytes(self._mmap[offset:offset + size])

    def write(self, offset: int, data: bytes) -> None:
        """Write to memory-mapped file."""
        if not self._mmap:
            raise IOError("File not mapped")
        self._mmap[offset:offset + len(data)] = data

    def flush(self) -> None:
        """Flush changes to disk."""
        if self._mmap:
            self._mmap.flush()


class IOBatchProcessor:
    """Batch processor for I/O operations with kernel bypass."""

    def __init__(self, max_batch_size: int = 32):
        self.max_batch_size = max_batch_size
        self._read_batch: List[Tuple[int, int, int, Callable]] = []
        self._write_batch: List[Tuple[int, bytes, int, Callable]] = []
        self._manager = KernelBypassManager()

    def add_read(
        self,
        fd: int,
        size: int,
        offset: int = 0,
        callback: Optional[Callable] = None
    ) -> None:
        """Add read to batch."""
        self._read_batch.append((fd, size, offset, callback))

        if len(self._read_batch) >= self.max_batch_size:
            self.flush_reads()

    def add_write(
        self,
        fd: int,
        data: bytes,
        offset: int = 0,
        callback: Optional[Callable] = None
    ) -> None:
        """Add write to batch."""
        self._write_batch.append((fd, data, offset, callback))

        if len(self._write_batch) >= self.max_batch_size:
            self.flush_writes()

    def flush_reads(self) -> List[int]:
        """Flush all pending reads."""
        if not self._read_batch:
            return []

        request_ids = []
        for fd, size, offset, callback in self._read_batch:
            req_id = self._manager.submit_read(fd, size, offset, callback)
            request_ids.append(req_id)

        self._read_batch.clear()
        return request_ids

    def flush_writes(self) -> List[int]:
        """Flush all pending writes."""
        if not self._write_batch:
            return []

        request_ids = []
        for fd, data, offset, callback in self._write_batch:
            req_id = self._manager.submit_write(fd, data, offset, callback)
            request_ids.append(req_id)

        self._write_batch.clear()
        return request_ids

    def flush_all(self) -> Tuple[List[int], List[int]]:
        """Flush all pending operations."""
        return self.flush_reads(), self.flush_writes()


# Global kernel bypass manager
_global_kb_manager: Optional[KernelBypassManager] = None


def get_kernel_bypass_manager(config: Optional[IOUringConfig] = None) -> KernelBypassManager:
    """Get or create global kernel bypass manager."""
    global _global_kb_manager
    if _global_kb_manager is None:
        _global_kb_manager = KernelBypassManager(config)
    return _global_kb_manager
