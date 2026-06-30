"""
PumpSwap calculation utilities.
100% port from Rust sol-trade-sdk (src/utils/calc/pumpswap.rs).
"""

from dataclasses import dataclass
from typing import Dict

# Maximum slippage in basis points (99.99%)
# This prevents the wrap amount from doubling when slippage is 100%
MAX_SLIPPAGE_BASIS_POINTS = 9999

# Fee basis points (from Rust: src/instruction/utils/pumpswap.rs accounts)
LP_FEE_BASIS_POINTS = 25
PROTOCOL_FEE_BASIS_POINTS = 5
COIN_CREATOR_FEE_BASIS_POINTS = 5


@dataclass(frozen=True)
class PumpSwapFeeBasisPoints:
    lp_fee_basis_points: int
    protocol_fee_basis_points: int
    coin_creator_fee_basis_points: int


def legacy_pumpswap_fee_basis_points(has_coin_creator: bool) -> PumpSwapFeeBasisPoints:
    return PumpSwapFeeBasisPoints(
        LP_FEE_BASIS_POINTS,
        PROTOCOL_FEE_BASIS_POINTS,
        COIN_CREATOR_FEE_BASIS_POINTS if has_coin_creator else 0,
    )


def ceil_div(a: int, b: int) -> int:
    """Ceiling division: (a + b - 1) // b"""
    if b == 0:
        return 0
    return (a + b - 1) // b


def compute_fee(amount: int, fee_basis_points: int) -> int:
    """Compute fee for a given amount using ceiling division"""
    return ceil_div(amount * fee_basis_points, 10_000)


def calculate_with_slippage_buy(amount: int, basis_points: int) -> int:
    """
    Calculate amount with slippage for buy operations.
    
    Slippage is clamped to MAX_SLIPPAGE_BASIS_POINTS (9999 = 99.99%)
    to prevent the amount from doubling when basis_points = 10000.
    
    Formula: amount + (amount * bps / 10000)
    """
    if amount == 0:
        return 0
    
    # Clamp basis points to max 9999 (99.99%) to prevent amount doubling at 100%
    bps = min(basis_points, MAX_SLIPPAGE_BASIS_POINTS)
    
    slippage_amount = (amount * bps) // 10_000
    return amount + slippage_amount


def calculate_with_slippage_sell(amount: int, basis_points: int) -> int:
    """
    Calculate amount with slippage for sell operations.
    
    100% from Rust: src/utils/calc/common.rs calculate_with_slippage_sell
    
    Formula: amount - (amount * basis_points / 10000)
    Returns 1 if amount <= basis_points / 10000 to ensure minimum output.
    """
    if amount == 0:
        return 0
    
    # Rust: if amount <= basis_points / 10000 { 1 } else { ... }
    if amount <= basis_points // 10_000:
        return 1
    
    slippage_amount = (amount * basis_points) // 10_000
    return amount - slippage_amount


def buy_quote_input_internal(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return buy_quote_input_internal_with_fees(
        quote_amount_in,
        slippage_basis_points,
        pool_base_reserves,
        pool_quote_reserves,
        legacy_pumpswap_fee_basis_points(has_coin_creator),
    )


def buy_quote_input_internal_with_fees(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    """
    Calculate base amount out for given quote amount in.
    
    100% port from Rust: src/utils/calc/pumpswap.rs buy_quote_input_internal()
    
    Returns dict with:
        - 'base': base_amount_out
        - 'internal_quote_without_fees': effective_quote  
        - 'max_quote': max_quote_amount_in with slippage
    """
    if quote_amount_in == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"base": 0, "internal_quote_without_fees": 0, "max_quote": 0}

    total_fee_bps = (
        fee_basis_points.lp_fee_basis_points
        + fee_basis_points.protocol_fee_basis_points
        + fee_basis_points.coin_creator_fee_basis_points
    )
    
    # Calculate effective quote after fees (Rust formula)
    # effective_quote = quote * 10000 / (10000 + total_fee_bps)
    denominator = 10_000 + total_fee_bps
    effective_quote = (quote_amount_in * 10_000) // denominator
    lp_fee = compute_fee(effective_quote, fee_basis_points.lp_fee_basis_points)
    protocol_fee = compute_fee(effective_quote, fee_basis_points.protocol_fee_basis_points)
    coin_creator_fee = compute_fee(effective_quote, fee_basis_points.coin_creator_fee_basis_points)
    total_with_fees = effective_quote + lp_fee + protocol_fee + coin_creator_fee
    if total_with_fees > quote_amount_in:
        effective_quote = max(0, effective_quote - (total_with_fees - quote_amount_in))
    input_amount = max(0, effective_quote - 1)

    # Constant product formula: base_out = (base_reserves * effective_quote) / (quote_reserves + effective_quote)
    numerator = pool_base_reserves * input_amount
    denominator_effective = pool_quote_reserves + input_amount

    if denominator_effective == 0:
        return {"base": 0, "internal_quote_without_fees": effective_quote, "max_quote": 0}

    base_amount_out = numerator // denominator_effective

    # Calculate max_quote with slippage (clamped)
    max_quote_amount_in = calculate_with_slippage_buy(quote_amount_in, slippage_basis_points)

    return {
        "base": base_amount_out,
        "internal_quote_without_fees": effective_quote,
        "max_quote": max_quote_amount_in,
    }


def buy_base_input_internal(
    base_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return buy_base_input_internal_with_fees(
        base_amount_out,
        slippage_basis_points,
        pool_base_reserves,
        pool_quote_reserves,
        legacy_pumpswap_fee_basis_points(has_coin_creator),
    )


def buy_base_input_internal_with_fees(
    base_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    """
    Calculate quote amount needed for given base output.
    
    100% port from Rust: src/utils/calc/pumpswap.rs buy_base_input_internal()
    
    Returns dict with:
        - 'internal_quote_amount': raw quote amount
        - 'ui_quote': total quote with fees
        - 'max_quote': max_quote_amount_in with slippage
    """
    if base_amount_out == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"internal_quote_amount": 0, "ui_quote": 0, "max_quote": 0}
    
    if base_amount_out > pool_base_reserves:
        return {"internal_quote_amount": 0, "ui_quote": 0, "max_quote": 0}
    
    # Constant product formula for input
    # quote_in = (quote_reserves * base_out) / (base_reserves - base_out)
    numerator = pool_quote_reserves * base_amount_out
    denominator = pool_base_reserves - base_amount_out
    
    if denominator == 0:
        return {"internal_quote_amount": 0, "ui_quote": 0, "max_quote": 0}
    
    quote_amount_in = ceil_div(numerator, denominator)
    
    # Calculate fees
    lp_fee = compute_fee(quote_amount_in, fee_basis_points.lp_fee_basis_points)
    protocol_fee = compute_fee(quote_amount_in, fee_basis_points.protocol_fee_basis_points)
    coin_creator_fee = compute_fee(quote_amount_in, fee_basis_points.coin_creator_fee_basis_points)
    
    total_quote = quote_amount_in + lp_fee + protocol_fee + coin_creator_fee
    
    # Apply slippage
    max_quote = calculate_with_slippage_buy(total_quote, slippage_basis_points)
    
    return {
        "internal_quote_amount": quote_amount_in,
        "ui_quote": total_quote,
        "max_quote": max_quote,
    }


def sell_base_input_internal(
    base_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return sell_base_input_internal_with_fees(
        base_amount_in,
        slippage_basis_points,
        pool_base_reserves,
        pool_quote_reserves,
        legacy_pumpswap_fee_basis_points(has_coin_creator),
    )


def sell_base_input_internal_with_fees(
    base_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    """
    Calculate quote amount out for given base amount in.
    
    100% port from Rust: src/utils/calc/pumpswap.rs sell_base_input_internal()
    
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
    lp_fee = compute_fee(quote_amount_out, fee_basis_points.lp_fee_basis_points)
    protocol_fee = compute_fee(quote_amount_out, fee_basis_points.protocol_fee_basis_points)
    coin_creator_fee = compute_fee(quote_amount_out, fee_basis_points.coin_creator_fee_basis_points)

    total_fees = lp_fee + protocol_fee + coin_creator_fee
    if total_fees > quote_amount_out:
        return {"ui_quote": 0, "min_quote": 0, "internal_quote_amount_out": quote_amount_out}
    
    final_quote = quote_amount_out - total_fees

    # Apply slippage (clamped)
    min_quote_amount_out = calculate_with_slippage_sell(final_quote, slippage_basis_points)

    return {
        "ui_quote": final_quote,
        "min_quote": min_quote_amount_out,
        "internal_quote_amount_out": quote_amount_out,
    }


def sell_quote_input_internal(
    quote_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return sell_quote_input_internal_with_fees(
        quote_amount_out,
        slippage_basis_points,
        pool_base_reserves,
        pool_quote_reserves,
        legacy_pumpswap_fee_basis_points(has_coin_creator),
    )


def sell_quote_input_internal_with_fees(
    quote_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    """
    Calculate base amount needed for given quote output.
    
    100% port from Rust: src/utils/calc/pumpswap.rs sell_quote_input_internal()
    
    Returns dict with:
        - 'internal_raw_quote': raw quote before reverse fee calculation
        - 'base': base amount needed
        - 'min_quote': min_quote with slippage
    """
    if quote_amount_out == 0 or pool_base_reserves == 0 or pool_quote_reserves == 0:
        return {"internal_raw_quote": 0, "base": 0, "min_quote": 0}
    
    if quote_amount_out > pool_quote_reserves:
        return {"internal_raw_quote": 0, "base": 0, "min_quote": 0}
    
    total_fee_bps = (
        fee_basis_points.lp_fee_basis_points
        + fee_basis_points.protocol_fee_basis_points
        + fee_basis_points.coin_creator_fee_basis_points
    )
    
    # Reverse the fee calculation
    denominator = 10_000 - total_fee_bps
    if denominator == 0:
        return {"internal_raw_quote": 0, "base": 0, "min_quote": 0}
    
    raw_quote = ceil_div(quote_amount_out * 10_000, denominator)
    
    if raw_quote >= pool_quote_reserves:
        return {"internal_raw_quote": raw_quote, "base": 0, "min_quote": 0}
    
    # Constant product for input
    # base_in = (base_reserves * raw_quote) / (quote_reserves - raw_quote)
    numerator = pool_base_reserves * raw_quote
    denominator = pool_quote_reserves - raw_quote
    
    if denominator == 0:
        return {"internal_raw_quote": raw_quote, "base": 0, "min_quote": 0}
    
    base_amount_in = ceil_div(numerator, denominator)
    
    # Apply slippage
    min_quote = calculate_with_slippage_sell(quote_amount_out, slippage_basis_points)
    
    return {
        "internal_raw_quote": raw_quote,
        "base": base_amount_in,
        "min_quote": min_quote,
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
