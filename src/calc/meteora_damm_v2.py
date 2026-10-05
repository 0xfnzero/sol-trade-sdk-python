"""
Meteora Damm V2 calculation utilities.
Based on sol-trade-sdk Rust implementation.
"""

from typing import Dict
from math import isqrt

def _u64(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError("Expected u64 integer")
    return value


def compute_swap_amount(
    token_a_reserve: int,
    token_b_reserve: int,
    is_a_to_b: bool,
    amount_in: int,
    slippage_basis_points: int,
) -> Dict[str, int]:
    """
    Compatibility constant-product estimate, not a DAMM v2 fee/sqrt-price quote.
    Returns dict with 'amount_out' and 'min_amount_out'.
    """
    for value in (token_a_reserve, token_b_reserve, amount_in, slippage_basis_points):
        _u64(value)
    if type(is_a_to_b) is not bool:
        raise ValueError("Direction must be boolean")
    if amount_in == 0:
        return {"amount_out": 0, "min_amount_out": 0}

    if is_a_to_b:
        # Swapping token A for token B
        if token_a_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: b_out = (b_reserve * a_in) / (a_reserve + a_in)
        numerator = token_b_reserve * amount_in
        denominator = token_a_reserve + amount_in

        if denominator == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        amount_out = numerator // denominator
    else:
        # Swapping token B for token A
        if token_b_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: a_out = (a_reserve * b_in) / (b_reserve + b_in)
        numerator = token_a_reserve * amount_in
        denominator = token_b_reserve + amount_in

        if denominator == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        amount_out = numerator // denominator

    # Apply slippage
    min_amount_out = amount_out - (amount_out * min(slippage_basis_points, 9999) // 10_000)

    return {
        "amount_out": amount_out,
        "min_amount_out": min_amount_out,
    }


def calculate_price(
    token_a_reserve: int,
    token_b_reserve: int,
) -> float:
    """Calculate current price (token B per token A)"""
    _u64(token_a_reserve)
    _u64(token_b_reserve)
    if token_a_reserve == 0:
        return 0.0
    return token_b_reserve / token_a_reserve


def calculate_liquidity(
    token_a_reserve: int,
    token_b_reserve: int,
) -> int:
    """Calculate liquidity (geometric mean of reserves)"""
    _u64(token_a_reserve)
    _u64(token_b_reserve)
    return isqrt(token_a_reserve * token_b_reserve)
