"""
PumpSwap calculation utilities.
Based on sol-trade-sdk Rust implementation.
"""

from typing import Dict

# Fee basis points
LP_FEE_BASIS_POINTS = 25
PROTOCOL_FEE_BASIS_POINTS = 5
COIN_CREATOR_FEE_BASIS_POINTS = 5


def compute_fee(amount: int, fee_basis_points: int) -> int:
    """Compute fee for a given amount"""
    return (amount * fee_basis_points) // 10_000


def buy_quote_input_internal(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    creator: bytes,
) -> Dict[str, int]:
    """
    Calculate base amount out for given quote amount in.
    Returns dict with 'base' (base_amount_out) and 'max_quote' (max_quote_amount_in with slippage).
    """
    if quote_amount_in == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"base": 0, "max_quote": 0}

    # Calculate fees
    total_fee_basis_points = LP_FEE_BASIS_POINTS + PROTOCOL_FEE_BASIS_POINTS
    has_creator = creator != bytes(32)
    if has_creator:
        total_fee_basis_points += COIN_CREATOR_FEE_BASIS_POINTS

    # Calculate input after fees
    fee = compute_fee(quote_amount_in, total_fee_basis_points)
    quote_amount_in_after_fee = quote_amount_in - fee

    # Constant product formula: base_out = (base_reserves * quote_in) / (quote_reserves + quote_in)
    numerator = pool_base_reserves * quote_amount_in_after_fee
    denominator = pool_quote_reserves + quote_amount_in_after_fee

    if denominator == 0:
        return {"base": 0, "max_quote": 0}

    base_amount_out = numerator // denominator

    # Apply slippage to get max_quote
    max_quote_amount_in = quote_amount_in + (quote_amount_in * slippage_basis_points // 10_000)

    return {
        "base": base_amount_out,
        "max_quote": max_quote_amount_in,
    }


def sell_base_input_internal(
    base_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    creator: bytes,
) -> Dict[str, int]:
    """
    Calculate quote amount out for given base amount in.
    Returns dict with 'min_quote' (min_quote_amount_out with slippage).
    """
    if base_amount_in == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"min_quote": 0}

    # Constant product formula: quote_out = (quote_reserves * base_in) / (base_reserves + base_in)
    numerator = pool_quote_reserves * base_amount_in
    denominator = pool_base_reserves + base_amount_in

    if denominator == 0:
        return {"min_quote": 0}

    quote_amount_out = numerator // denominator

    # Calculate fees
    total_fee_basis_points = LP_FEE_BASIS_POINTS + PROTOCOL_FEE_BASIS_POINTS
    has_creator = creator != bytes(32)
    if has_creator:
        total_fee_basis_points += COIN_CREATOR_FEE_BASIS_POINTS

    fee = compute_fee(quote_amount_out, total_fee_basis_points)
    quote_amount_out_after_fee = quote_amount_out - fee

    # Apply slippage
    min_quote_amount_out = quote_amount_out_after_fee - (quote_amount_out_after_fee * slippage_basis_points // 10_000)

    return {
        "min_quote": min_quote_amount_out,
    }


def calculate_price_impact(
    amount_in: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
) -> float:
    """Calculate price impact as a percentage"""
    if pool_base_reserves == 0 or pool_quote_reserves == 0:
        return 0.0

    # Current price
    current_price = pool_quote_reserves / pool_base_reserves

    # Price after trade
    new_base_reserves = pool_base_reserves + amount_in
    new_quote_reserves = (pool_base_reserves * pool_quote_reserves) // new_base_reserves

    if new_base_reserves == 0:
        return 0.0

    new_price = new_quote_reserves / new_base_reserves

    # Price impact
    if current_price == 0:
        return 0.0

    price_impact = abs(new_price - current_price) / current_price * 100
    return price_impact
