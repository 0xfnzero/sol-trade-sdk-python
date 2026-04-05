"""
PumpSwap calculation utilities.
Based on sol-trade-sdk Rust implementation (src/utils/calc/pumpswap.rs).
"""

from typing import Dict

# Fee basis points (from Rust: src/instruction/utils/pumpswap.rs accounts)
LP_FEE_BASIS_POINTS = 25
PROTOCOL_FEE_BASIS_POINTS = 5
COIN_CREATOR_FEE_BASIS_POINTS = 5


def ceil_div(a: int, b: int) -> int:
    """Ceiling division: (a + b - 1) // b"""
    return (a + b - 1) // b


def compute_fee(amount: int, fee_basis_points: int) -> int:
    """Compute fee for a given amount using ceiling division"""
    return ceil_div(amount * fee_basis_points, 10_000)


def buy_quote_input_internal(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    creator: bytes,
) -> Dict[str, int]:
    """
    Calculate base amount out for given quote amount in.
    
    Matches Rust implementation in src/utils/calc/pumpswap.rs buy_quote_input_internal()
    
    Returns dict with:
        - 'base': base_amount_out
        - 'internal_quote_without_fees': effective_quote  
        - 'max_quote': max_quote_amount_in with slippage
    """
    if quote_amount_in == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"base": 0, "internal_quote_without_fees": 0, "max_quote": 0}

    # Calculate total fee basis points (Rust: LP_FEE + PROTOCOL_FEE + COIN_CREATOR_FEE)
    total_fee_bps = LP_FEE_BASIS_POINTS + PROTOCOL_FEE_BASIS_POINTS
    has_creator = creator != bytes(32)
    if has_creator:
        total_fee_bps += COIN_CREATOR_FEE_BASIS_POINTS
    
    # Calculate effective quote after fees (Rust formula)
    # effective_quote = quote * 10000 / (10000 + total_fee_bps)
    denominator = 10_000 + total_fee_bps
    effective_quote = (quote_amount_in * 10_000) // denominator

    # Constant product formula: base_out = (base_reserves * effective_quote) / (quote_reserves + effective_quote)
    numerator = pool_base_reserves * effective_quote
    denominator_effective = pool_quote_reserves + effective_quote

    if denominator_effective == 0:
        return {"base": 0, "internal_quote_without_fees": effective_quote, "max_quote": 0}

    base_amount_out = numerator // denominator_effective

    # Calculate max_quote with slippage
    max_quote_amount_in = quote_amount_in + (quote_amount_in * slippage_basis_points // 10_000)

    return {
        "base": base_amount_out,
        "internal_quote_without_fees": effective_quote,
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
    
    Matches Rust implementation in src/utils/calc/pumpswap.rs sell_base_input_internal()
    
    Returns dict with:
        - 'ui_quote': final quote after fees
        - 'min_quote': min_quote_amount_out with slippage
        - 'internal_quote_amount_out': raw quote before fees
    """
    if base_amount_in == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"ui_quote": 0, "min_quote": 0, "internal_quote_amount_out": 0}

    # Constant product formula: quote_out = (quote_reserves * base_in) / (base_reserves + base_in)
    numerator = pool_quote_reserves * base_amount_in
    denominator = pool_base_reserves + base_amount_in

    if denominator == 0:
        return {"ui_quote": 0, "min_quote": 0, "internal_quote_amount_out": 0}

    quote_amount_out = numerator // denominator

    # Calculate fees (Rust computes each fee separately)
    lp_fee = compute_fee(quote_amount_out, LP_FEE_BASIS_POINTS)
    protocol_fee = compute_fee(quote_amount_out, PROTOCOL_FEE_BASIS_POINTS)
    
    has_creator = creator != bytes(32)
    coin_creator_fee = 0
    if has_creator:
        coin_creator_fee = compute_fee(quote_amount_out, COIN_CREATOR_FEE_BASIS_POINTS)

    total_fees = lp_fee + protocol_fee + coin_creator_fee
    if total_fees > quote_amount_out:
        return {"ui_quote": 0, "min_quote": 0, "internal_quote_amount_out": quote_amount_out}
    
    final_quote = quote_amount_out - total_fees

    # Apply slippage
    min_quote_amount_out = final_quote - (final_quote * slippage_basis_points // 10_000)

    return {
        "ui_quote": final_quote,
        "min_quote": min_quote_amount_out,
        "internal_quote_amount_out": quote_amount_out,
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
