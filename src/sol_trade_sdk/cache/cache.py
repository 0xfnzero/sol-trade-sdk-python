"""
High-Performance Cache Implementation for Sol Trade SDK
Provides LRU, TTL, and sharded caches for optimal performance.
"""

from typing import Any, Optional, Dict, Generic, TypeVar, Callable
from dataclasses import dataclass, field
from threading import RLock, Lock
from collections import OrderedDict
from time import time
from functools import wraps
import heapq

K = TypeVar('K')
V = TypeVar('V')


@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


@dataclass
class CacheEntry(Generic[V]):
    """Cache entry with TTL support"""
    value: V
    expiration: float
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time() > self.expiration


class LRUCache(Generic[K, V]):
    """
    Thread-safe LRU cache with TTL support.
    
    Features:
    - O(1) get and set operations
    - Automatic eviction when full
    - TTL-based expiration
    - Statistics tracking
    """

    def __init__(self, max_size: int = 1000, ttl: float = 300.0):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries
            ttl: Time-to-live in seconds
        """
        self._max_size = max_size
        self._ttl = ttl
        self._cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self._lock = RLock()
        self._stats = CacheStats()

    def get(self, key: K) -> Optional[V]:
        """Get a value from the cache"""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access_count += 1
            self._stats.hits += 1
            return entry.value

    def set(self, key: K, value: V) -> None:
        """Set a value in the cache"""
        with self._lock:
            expiration = time() + self._ttl

            if key in self._cache:
                self._cache[key].value = value
                self._cache[key].expiration = expiration
                self._cache.move_to_end(key)
            else:
                self._cache[key] = CacheEntry(
                    value=value,
                    expiration=expiration,
                )

                # Evict if over capacity
                while len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)
                    self._stats.evictions += 1

            self._stats.size = len(self._cache)

    def delete(self, key: K) -> bool:
        """Delete a key from the cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False

    def clear(self) -> None:
        """Clear all entries"""
        with self._lock:
            self._cache.clear()
            self._stats.size = 0

    def cleanup(self) -> int:
        """Remove expired entries, returns count of removed entries"""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired
            ]
            for key in expired_keys:
                del self._cache[key]
                self._stats.evictions += 1
            self._stats.size = len(self._cache)
            return len(expired_keys)

    @property
    def stats(self) -> CacheStats:
        """Get cache statistics"""
        return self._stats


class TTLCache(Generic[K, V]):
    """
    Simple TTL cache with background cleanup support.
    Optimized for read-heavy workloads.
    """

    def __init__(self, ttl: float = 300.0):
        self._ttl = ttl
        self._cache: Dict[K, CacheEntry[V]] = {}
        self._lock = RLock()
        self._stats = CacheStats()

    def get(self, key: K) -> Optional[V]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._stats.misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._stats.misses += 1
                return None

            self._stats.hits += 1
            return entry.value

    def set(self, key: K, value: V) -> None:
        with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                expiration=time() + self._ttl,
            )
            self._stats.size = len(self._cache)

    def delete(self, key: K) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.size = len(self._cache)
                return True
            return False

    def cleanup(self) -> int:
        with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired]
            for k in expired:
                del self._cache[k]
            self._stats.size = len(self._cache)
            return len(expired)


class ShardedCache(Generic[K, V]):
    """
    Sharded cache for high concurrency scenarios.
    Distributes keys across multiple shards to reduce lock contention.
    """

    def __init__(self, shards: int = 16, max_size_per_shard: int = 1000, ttl: float = 300.0):
        self._shards = [
            LRUCache[K, V](max_size=max_size_per_shard, ttl=ttl)
            for _ in range(shards)
        ]
        self._shard_mask = shards - 1

    def _get_shard(self, key: K) -> LRUCache[K, V]:
        """Get the shard for a key using consistent hashing"""
        # Simple hash - can be improved with MurmurHash3
        hash_value = hash(str(key))
        return self._shards[hash_value & self._shard_mask]

    def get(self, key: K) -> Optional[V]:
        return self._get_shard(key).get(key)

    def set(self, key: K, value: V) -> None:
        self._get_shard(key).set(key, value)

    def delete(self, key: K) -> bool:
        return self._get_shard(key).delete(key)

    def clear(self) -> None:
        for shard in self._shards:
            shard.clear()

    @property
    def stats(self) -> CacheStats:
        """Aggregate statistics from all shards"""
        total = CacheStats()
        for shard in self._shards:
            total.hits += shard.stats.hits
            total.misses += shard.stats.misses
            total.evictions += shard.stats.evictions
            total.size += shard.stats.size
        return total


# ===== Decorator for Function Caching =====

def cached(
    cache: Optional[LRUCache] = None,
    key_func: Optional[Callable] = None,
    ttl: float = 300.0,
    max_size: int = 1000,
):
    """
    Decorator for caching function results.
    
    Usage:
        @cached(ttl=60)
        def expensive_function(arg):
            return arg * 2
    """
    if cache is None:
        cache = LRUCache(max_size=max_size, ttl=ttl)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                key = key_func(*args, **kwargs)
            else:
                key = (func.__name__, args, tuple(sorted(kwargs.items())))

            result = cache.get(key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache
        return wrapper

    return decorator


# ===== Pre-configured Caches =====

# Global caches for common use cases
_blockhash_cache = TTLCache[str, str](ttl=2.0)  # 2 second TTL for blockhashes
_account_cache = ShardedCache[str, bytes](shards=16, max_size_per_shard=500, ttl=10.0)
_price_cache = TTLCache[str, float](ttl=1.0)  # 1 second TTL for prices


def get_blockhash_cache() -> TTLCache[str, str]:
    """Get the global blockhash cache"""
    return _blockhash_cache


def get_account_cache() -> ShardedCache[str, bytes]:
    """Get the global account cache"""
    return _account_cache


def get_price_cache() -> TTLCache[str, float]:
    """Get the global price cache"""
    return _price_cache
