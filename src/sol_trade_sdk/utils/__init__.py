"""
Utilities for Sol Trade SDK
"""

from __future__ import annotations

import time
from typing import TypeVar, Callable, Optional
from solders.pubkey import Pubkey

T = TypeVar("T")


def calculate_with_slippage_buy(amount: int, slippage_basis_points: int) -> int:
    """Calculate amount with slippage for buy operations"""
    return amount * (10000 + slippage_basis_points) // 10000


def calculate_with_slippage_sell(amount: int, slippage_basis_points: int) -> int:
    """Calculate amount with slippage for sell operations"""
    return amount * (10000 - slippage_basis_points) // 10000


def lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL"""
    return lamports / 1_000_000_000


def sol_to_lamports(sol: float) -> int:
    """Convert SOL to lamports"""
    return int(sol * 1_000_000_000)


def now_microseconds() -> int:
    """Get current timestamp in microseconds"""
    return int(time.time() * 1_000_000)


def is_valid_public_key(key: str) -> bool:
    """Validate public key string"""
    try:
        Pubkey.from_string(key)
        return True
    except Exception:
        return False


def format_public_key(key: Pubkey | str, chars: int = 8) -> str:
    """Format public key for display (truncated)"""
    key_str = str(key)
    if len(key_str) <= chars * 2:
        return key_str
    return f"{key_str[:chars]}...{key_str[-chars:]}"


def calculate_price_impact(reserve_in: int, amount_in: int) -> float:
    """Calculate price impact percentage"""
    return (amount_in * 10000) / reserve_in / 100


async def retry_with_backoff(
    fn: Callable[[], T],
    max_retries: int = 3,
    base_delay_ms: int = 1000,
) -> T:
    """
    Retry a function with exponential backoff.

    Args:
        fn: Function to retry
        max_retries: Maximum number of retries
        base_delay_ms: Base delay in milliseconds

    Returns:
        Result of the function

    Raises:
        Last error if all retries fail
    """
    import asyncio

    last_error: Optional[Exception] = None

    for i in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            last_error = e
            if i < max_retries - 1:
                delay = base_delay_ms * (2**i) / 1000
                await asyncio.sleep(delay)

    raise last_error
