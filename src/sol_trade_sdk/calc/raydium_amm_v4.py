"""
Raydium AMM V4 calculation utilities.
Based on sol-trade-sdk Rust implementation.
"""

from typing import Dict


def compute_swap_amount(
    coin_reserve: int,
    pc_reserve: int,
    is_coin_to_pc: bool,
    amount_in: int,
    slippage_basis_points: int,
) -> Dict[str, int]:
    """
    Compute swap amount for Raydium AMM V4.
    Returns dict with 'amount_out' and 'min_amount_out'.
    """
    if amount_in == 0:
        return {"amount_out": 0, "min_amount_out": 0}

    if is_coin_to_pc:
        # Swapping coin (base) for pc (quote)
        if coin_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: pc_out = (pc_reserve * coin_in) / (coin_reserve + coin_in)
        numerator = pc_reserve * amount_in
        denominator = coin_reserve + amount_in

        if denominator == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        amount_out = numerator // denominator
    else:
        # Swapping pc (quote) for coin (base)
        if pc_reserve == 0:
            return {"amount_out": 0, "min_amount_out": 0}

        # Constant product: coin_out = (coin_reserve * pc_in) / (pc_reserve + pc_in)
        numerator = coin_reserve * amount_in
        denominator = pc_reserve + amount_in

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
    coin_reserve: int,
    pc_reserve: int,
) -> float:
    """Calculate current price (pc per coin)"""
    if coin_reserve == 0:
        return 0.0
    return pc_reserve / coin_reserve
