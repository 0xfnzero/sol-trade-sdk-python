"""
Compute Budget Manager - Caching compute budget instructions.
Based on sol-trade-sdk Rust implementation patterns.
"""

import threading
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass

# ===== Constants =====

# ComputeBudgetProgram is the Solana compute budget program ID
COMPUTE_BUDGET_PROGRAM = bytes([
    0x43, 0x6f, 0x6d, 0x70, 0x75, 0x74, 0x65, 0x42,
    0x75, 0x64, 0x67, 0x65, 0x74, 0x31, 0x31, 0x31,
    0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31,
    0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31, 0x31,
])

# Instruction discriminators
SET_COMPUTE_UNIT_PRICE_DISCRIMINATOR = bytes([0x02, 0x00, 0x00, 0x00])
SET_COMPUTE_UNIT_LIMIT_DISCRIMINATOR = bytes([0x00, 0x00, 0x00, 0x00])


# ===== Cache Key =====

@dataclass(frozen=True)
class ComputeBudgetCacheKey:
    """Cache key for compute budget instructions"""
    unit_price: int
    unit_limit: int


# ===== Cache =====

class ComputeBudgetCache:
    """
    Stores compute budget instructions.
    Uses RLock for high-performance concurrent access.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: Dict[ComputeBudgetCacheKey, Tuple[bytes, ...]] = {}


# Global cache instance
_global_cache = ComputeBudgetCache()


# ===== Instruction Builders =====

def set_compute_unit_price(price: int) -> bytes:
    """Create set compute unit price instruction"""
    # Instruction: [discriminator (4 bytes) | price (8 bytes)]
    data = bytearray(12)
    data[0:4] = SET_COMPUTE_UNIT_PRICE_DISCRIMINATOR
    # Little-endian price
    data[4:12] = price.to_bytes(8, 'little')
    return bytes(data)


def set_compute_unit_limit(limit: int) -> bytes:
    """Create set compute unit limit instruction"""
    # Instruction: [discriminator (4 bytes) | limit (4 bytes)]
    data = bytearray(8)
    data[0:4] = SET_COMPUTE_UNIT_LIMIT_DISCRIMINATOR
    # Little-endian limit
    data[4:8] = limit.to_bytes(4, 'little')
    return bytes(data)


# ===== Cached Instruction Functions =====

def extend_compute_budget_instructions(
    instructions: List[bytes],
    unit_price: int,
    unit_limit: int,
) -> List[bytes]:
    """
    Extend instructions with compute budget instructions.
    On cache hit, extends from cached tuple (no allocation).
    """
    cache_key = ComputeBudgetCacheKey(unit_price, unit_limit)

    # Check cache
    with _global_cache._lock:
        if cache_key in _global_cache._cache:
            cached = _global_cache._cache[cache_key]
            instructions.extend(cached)
            return instructions

    # Build new instructions
    insts = []
    if unit_price > 0:
        insts.append(set_compute_unit_price(unit_price))
    if unit_limit > 0:
        insts.append(set_compute_unit_limit(unit_limit))

    # Store in cache
    cached = tuple(insts)
    with _global_cache._lock:
        _global_cache._cache[cache_key] = cached

    instructions.extend(cached)
    return instructions


def compute_budget_instructions(unit_price: int, unit_limit: int) -> List[bytes]:
    """
    Returns compute budget instructions.
    Note: prefer extend_compute_budget_instructions on hot path.
    """
    cache_key = ComputeBudgetCacheKey(unit_price, unit_limit)

    # Check cache
    with _global_cache._lock:
        if cache_key in _global_cache._cache:
            cached = _global_cache._cache[cache_key]
            return list(cached)  # Return copy

    # Build new instructions
    insts = []
    if unit_price > 0:
        insts.append(set_compute_unit_price(unit_price))
    if unit_limit > 0:
        insts.append(set_compute_unit_limit(unit_limit))

    # Store in cache
    cached = tuple(insts)
    with _global_cache._lock:
        _global_cache._cache[cache_key] = cached

    return insts


# ===== Cache Statistics =====

def get_cache_stats() -> int:
    """Get cache size"""
    with _global_cache._lock:
        return len(_global_cache._cache)


def clear_cache() -> None:
    """Clear the cache (for testing)"""
    with _global_cache._lock:
        _global_cache._cache.clear()


# ===== Manager Class =====

class ComputeBudgetManager:
    """
    High-level manager for compute budget instructions.
    Provides caching and convenience methods.
    """

    def __init__(self):
        self._cache = ComputeBudgetCache()

    def get_compute_budget_instructions(
        self,
        cu_limit: int,
        cu_price: int,
    ) -> List[bytes]:
        """Get compute budget instructions (cached)"""
        return compute_budget_instructions(cu_price, cu_limit)

    def get_compute_budget_instructions_with_tip(
        self,
        cu_limit: int,
        cu_price: int,
        tip: int,
    ) -> List[bytes]:
        """Get compute budget instructions with priority fee tip"""
        ixs = self.get_compute_budget_instructions(cu_limit, cu_price)
        if tip > 0:
            # Add priority fee instruction (simplified)
            ixs.append(set_compute_unit_price(tip))
        return ixs

    def clear_cache(self) -> None:
        """Clear the cache"""
        clear_cache()
