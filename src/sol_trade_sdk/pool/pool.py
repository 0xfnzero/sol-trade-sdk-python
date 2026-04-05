"""
High-Performance Pool and Concurrency Utilities for Sol Trade SDK
"""

from typing import TypeVar, Generic, Callable, Optional, List, Any
from dataclasses import dataclass, field
from threading import Lock, RLock, Semaphore
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, Empty
from contextlib import contextmanager
import time
import asyncio
from abc import ABC, abstractmethod

T = TypeVar('T')
R = TypeVar('R')


# ===== Worker Pool =====

class WorkerPool:
    """
    High-performance worker pool for parallel task execution.
    
    Features:
    - Dynamic task submission
    - Batch processing support
    - Graceful shutdown
    - Statistics tracking
    """

    def __init__(self, workers: int = 4, queue_size: int = 100):
        self._workers = workers
        self._queue_size = queue_size
        self._task_queue: Queue = Queue(maxsize=queue_size)
        self._result_queue: Queue = Queue()
        self._executor = ThreadPoolExecutor(max_workers=workers)
        self._active_tasks = 0
        self._tasks_completed = 0
        self._lock = Lock()
        self._shutdown = False

    def submit(self, task: Callable[[], R]) -> Future:
        """Submit a task to the pool"""
        if self._shutdown:
            raise RuntimeError("Pool is shut down")

        def wrapper():
            with self._lock:
                self._active_tasks += 1
            try:
                result = task()
                with self._lock:
                    self._tasks_completed += 1
                return result
            finally:
                with self._lock:
                    self._active_tasks -= 1

        return self._executor.submit(wrapper)

    def submit_batch(self, tasks: List[Callable[[], R]]) -> List[Future]:
        """Submit multiple tasks and return futures"""
        return [self.submit(task) for task in tasks]

    def map(self, func: Callable[[T], R], items: List[T]) -> List[R]:
        """Map a function over items in parallel"""
        futures = [self.submit(lambda i=i: func(i)) for i in items]
        return [f.result() for f in futures]

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the pool"""
        self._shutdown = True
        self._executor.shutdown(wait=wait)

    @property
    def stats(self) -> dict:
        """Get pool statistics"""
        with self._lock:
            return {
                "active_tasks": self._active_tasks,
                "tasks_completed": self._tasks_completed,
                "queue_size": self._queue_size,
            }


# ===== Connection Pool =====

class Connection(ABC):
    """Abstract connection interface"""

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def is_alive(self) -> bool:
        pass


class ConnectionPool(Generic[T]):
    """
    Generic connection pool with automatic management.
    
    Features:
    - Connection reuse
    - Automatic cleanup of dead connections
    - Configurable pool size
    - Wait timeout when pool exhausted
    """

    def __init__(
        self,
        factory: Callable[[], T],
        max_size: int = 10,
        timeout: float = 30.0,
    ):
        self._factory = factory
        self._max_size = max_size
        self._timeout = timeout
        self._pool: List[T] = []
        self._created = 0
        self._waiting = 0
        self._lock = RLock()
        self._semaphore = Semaphore(max_size)

    @contextmanager
    def get(self) -> T:
        """Get a connection from the pool (context manager)"""
        conn = self._acquire()
        try:
            yield conn
        finally:
            self._release(conn)

    def _acquire(self) -> T:
        """Acquire a connection"""
        acquired = self._semaphore.acquire(timeout=self._timeout)
        if not acquired:
            raise TimeoutError("Connection pool exhausted")

        with self._lock:
            if self._pool:
                conn = self._pool.pop()
                if hasattr(conn, 'is_alive') and not conn.is_alive():
                    self._created -= 1
                    return self._create_new()
                return conn
            return self._create_new()

    def _release(self, conn: T) -> None:
        """Release a connection back to the pool"""
        with self._lock:
            if hasattr(conn, 'is_alive') and not conn.is_alive():
                self._created -= 1
            else:
                self._pool.append(conn)
        self._semaphore.release()

    def _create_new(self) -> T:
        """Create a new connection"""
        if self._created >= self._max_size:
            raise RuntimeError("Max connections reached")
        self._created += 1
        return self._factory()

    def close_all(self) -> None:
        """Close all connections"""
        with self._lock:
            for conn in self._pool:
                if hasattr(conn, 'close'):
                    conn.close()
            self._pool.clear()
            self._created = 0

    @property
    def stats(self) -> dict:
        """Get pool statistics"""
        with self._lock:
            return {
                "created": self._created,
                "available": len(self._pool),
                "max_size": self._max_size,
            }


# ===== Rate Limiter =====

class RateLimiter:
    """
    Token bucket rate limiter.
    
    Features:
    - Smooth rate limiting
    - Burst handling
    - Thread-safe
    """

    def __init__(self, rate: float, burst: int = 10):
        """
        Initialize rate limiter.
        
        Args:
            rate: Requests per second
            burst: Maximum burst size
        """
        self._rate = rate
        self._burst = burst
        self._tokens = burst
        self._last_update = time.monotonic()
        self._lock = Lock()

    def allow(self) -> bool:
        """Check if a request is allowed"""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._last_update = now

            # Add tokens based on elapsed time
            self._tokens += elapsed * self._rate
            if self._tokens > self._burst:
                self._tokens = self._burst

            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    def wait(self) -> None:
        """Wait until a request is allowed"""
        while not self.allow():
            time.sleep(0.001)  # Small sleep to avoid busy-waiting


class MultiRateLimiter:
    """
    Rate limiter with multiple keys.
    Useful for per-endpoint or per-user rate limiting.
    """

    def __init__(self, rate: float, burst: int = 10):
        self._rate = rate
        self._burst = burst
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        """Check if a request is allowed for a key"""
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(self._rate, self._burst)
            return self._limiters[key].allow()


# ===== Async Utilities =====

class AsyncWorkerPool:
    """Async worker pool for async tasks"""

    def __init__(self, workers: int = 4):
        self._workers = workers
        self._semaphore = asyncio.Semaphore(workers)
        self._active = 0
        self._completed = 0
        self._lock = asyncio.Lock()

    async def submit(self, task: Callable[[], R]) -> R:
        """Submit an async task"""
        async with self._semaphore:
            async with self._lock:
                self._active += 1
            try:
                result = await task()
                async with self._lock:
                    self._completed += 1
                return result
            finally:
                async with self._lock:
                    self._active -= 1

    async def map(self, func: Callable[[T], R], items: List[T]) -> List[R]:
        """Map an async function over items"""
        tasks = [self.submit(lambda i=i: func(i)) for i in items]
        return await asyncio.gather(*tasks)

    @property
    async def stats(self) -> dict:
        async with self._lock:
            return {
                "active": self._active,
                "completed": self._completed,
                "workers": self._workers,
            }


# ===== Object Pool =====

class ObjectPool(Generic[T]):
    """
    Generic object pool for reusing expensive objects.
    """

    def __init__(
        self,
        factory: Callable[[], T],
        reset_func: Optional[Callable[[T], None]] = None,
        max_size: int = 100,
    ):
        self._factory = factory
        self._reset_func = reset_func
        self._max_size = max_size
        self._pool: Queue[T] = Queue(maxsize=max_size)
        self._created = 0
        self._lock = Lock()

    def acquire(self) -> T:
        """Acquire an object from the pool"""
        try:
            obj = self._pool.get_nowait()
            return obj
        except Empty:
            with self._lock:
                self._created += 1
            return self._factory()

    def release(self, obj: T) -> None:
        """Release an object back to the pool"""
        if self._reset_func:
            self._reset_func(obj)
        try:
            self._pool.put_nowait(obj)
        except:
            pass  # Pool is full, discard object

    @contextmanager
    def use(self) -> T:
        """Context manager for pool objects"""
        obj = self.acquire()
        try:
            yield obj
        finally:
            self.release(obj)
