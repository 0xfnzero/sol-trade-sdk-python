"""
Compute Budget Module for Sol Trade SDK

Provides cached compute budget instructions for low-latency transaction building.
"""

from .compute_budget_manager import (
    # Constants
    COMPUTE_BUDGET_PROGRAM,
    SET_COMPUTE_UNIT_PRICE_DISCRIMINATOR,
    SET_COMPUTE_UNIT_LIMIT_DISCRIMINATOR,
    
    # Cache key
    ComputeBudgetCacheKey,
    
    # Instruction builders
    set_compute_unit_price,
    set_compute_unit_limit,
    
    # Cached functions
    extend_compute_budget_instructions,
    compute_budget_instructions,
    
    # Cache stats
    get_cache_stats,
    clear_cache,
)

__all__ = [
    # Constants
    'COMPUTE_BUDGET_PROGRAM',
    'SET_COMPUTE_UNIT_PRICE_DISCRIMINATOR',
    'SET_COMPUTE_UNIT_LIMIT_DISCRIMINATOR',
    
    # Cache key
    'ComputeBudgetCacheKey',
    
    # Instruction builders
    'set_compute_unit_price',
    'set_compute_unit_limit',
    
    # Cached functions
    'extend_compute_budget_instructions',
    'compute_budget_instructions',
    
    # Cache stats
    'get_cache_stats',
    'clear_cache',
]
