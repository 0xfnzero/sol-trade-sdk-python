"""
Fast functions with caching.
Based on sol-trade-sdk Rust implementation.
"""

import threading
from typing import Dict, List, Tuple, Callable
from functools import lru_cache

# Instruction cache
_instruction_cache: Dict[tuple, List[bytes]] = {}
_instruction_lock = threading.RLock()

# PDA cache
_pda_cache: Dict[tuple, bytes] = {}
_pda_lock = threading.RLock()

# ATA cache
_ata_cache: Dict[tuple, bytes] = {}
_ata_lock = threading.RLock()


def get_cached_instructions(
    cache_key: tuple,
    compute_fn: Callable[[], List[bytes]],
) -> List[bytes]:
    """Get cached instruction or compute and cache"""
    with _instruction_lock:
        if cache_key in _instruction_cache:
            return _instruction_cache[cache_key].copy()
        
        result = compute_fn()
        _instruction_cache[cache_key] = result.copy()
        return result


def create_associated_token_account_idempotent_fast(
    payer: bytes,
    owner: bytes,
    mint: bytes,
    token_program: bytes,
) -> List[bytes]:
    """Fast ATA creation with caching"""
    cache_key = (payer, owner, mint, token_program, False)
    
    def compute():
        # Get ATA address
        ata = get_associated_token_address_fast(owner, mint, token_program)
        
        # Create instruction data
        # [1] = create idempotent
        return [bytes([1]) + payer + ata + owner + mint + token_program]
    
    return get_cached_instructions(cache_key, compute)


def get_associated_token_address_fast(
    owner: bytes,
    mint: bytes,
    token_program: bytes,
) -> bytes:
    """Fast ATA address derivation with caching"""
    cache_key = (owner, mint, token_program)
    
    with _ata_lock:
        if cache_key in _ata_cache:
            return _ata_cache[cache_key]
        
        # Derive ATA (simplified - would use proper PDA derivation)
        # ATA = find_program_address([owner, token_program, mint], associated_token_program)
        result = bytes(32)  # Placeholder
        _ata_cache[cache_key] = result
        return result


def clear_caches():
    """Clear all caches (for testing)"""
    with _instruction_lock:
        _instruction_cache.clear()
    with _pda_lock:
        _pda_cache.clear()
    with _ata_lock:
        _ata_cache.clear()
