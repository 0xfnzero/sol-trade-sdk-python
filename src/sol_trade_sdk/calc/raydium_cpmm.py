"""
Raydium CPMM calculation utilities.
Based on sol-trade-sdk Rust implementation.
"""

from typing import Dict


def compute_swap_amount(
    base_reserve: int,
    quote_reserve: int,
    is_base_in: bool,
    amount_in: int,
    slippage_basis_points: int,
) -> Dict[str, int]:
    """
    Compute swap amount and minimum output with slippage.
    Returns dict with 'amount_out' and 'min_amount_out'.
    """
    if amount_in == 0:
        return {"amount_out": 0, "min_amount_out": 0}

    if is_base_in:
        # Swapping base for quote
        if base_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: quote_out = (quote_reserve * base_in) / (base_reserve + base_in)
        numerator = quote_reserve * amount_in
        denominator = base_reserve + amount_in

        if denominator == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        amount_out = numerator // denominator
    else:
        # Swapping quote for base
        if quote_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: base_out = (base_reserve * quote_in) / (quote_reserve + quote_in)
        numerator = base_reserve * amount_in
        denominator = quote_reserve + amount_in

        if denominator == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        amount_out = numerator // denominator

    # Apply slippage
    min_amount_out = amount_out - (amount_out * slippage_basis_points // 10_000)

    return {
        "amount_out": amount_out,
        "min_amount_out": min_amount_out,
    }


def calculate_price(
    base_reserve: int,
    quote_reserve: int,
) -> float:
    """Calculate current price (quote per base)"""
    if base_reserve == 0:
        return 0.0
    return quote_reserve / base_reserve


def calculate_liquidity(
    base_reserve: int,
    quote_reserve: int,
) -> int:
    """Calculate liquidity (geometric mean of reserves)"""
    import math
    return int(math.sqrt(base_reserve * quote_reserve))
