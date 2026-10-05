"""Compatibility dictionary API backed by the shared native PumpSwap quote core."""
from dataclasses import asdict
from typing import Dict
try:
    from . import (PumpSwapFeeBasisPoints, legacy_pumpswap_fee_basis_points, ceil_div,
        compute_fee, effective_quote_reserves, calculate_with_slippage_buy,
        calculate_with_slippage_sell, MAX_SLIPPAGE_BASIS_POINTS, U64_MAX, I128_MIN, I128_MAX,
        PUMPSWAP_LP_FEE_BASIS_POINTS as LP_FEE_BASIS_POINTS,
        PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS as PROTOCOL_FEE_BASIS_POINTS,
        PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS as COIN_CREATOR_FEE_BASIS_POINTS)
    from . import (buy_quote_input_internal as _buy_quote, buy_base_input_internal as _buy_base,
        sell_base_input_internal as _sell_base, sell_quote_input_internal as _sell_quote,
        buy_quote_input_internal_with_fees as _buy_quote_fees,
        buy_base_input_internal_with_fees as _buy_base_fees,
        sell_base_input_internal_with_fees as _sell_base_fees,
        sell_quote_input_internal_with_fees as _sell_quote_fees)
except ImportError:  # Standalone compatibility import used by older examples.
    from sol_trade_sdk.calc import (PumpSwapFeeBasisPoints, legacy_pumpswap_fee_basis_points, ceil_div,
        compute_fee, effective_quote_reserves, calculate_with_slippage_buy,
        calculate_with_slippage_sell, MAX_SLIPPAGE_BASIS_POINTS, U64_MAX, I128_MIN, I128_MAX,
        PUMPSWAP_LP_FEE_BASIS_POINTS as LP_FEE_BASIS_POINTS,
        PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS as PROTOCOL_FEE_BASIS_POINTS,
        PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS as COIN_CREATOR_FEE_BASIS_POINTS)
    from sol_trade_sdk.calc import (buy_quote_input_internal as _buy_quote, buy_base_input_internal as _buy_base,
        sell_base_input_internal as _sell_base, sell_quote_input_internal as _sell_quote,
        buy_quote_input_internal_with_fees as _buy_quote_fees,
        buy_base_input_internal_with_fees as _buy_base_fees,
        sell_base_input_internal_with_fees as _sell_base_fees,
        sell_quote_input_internal_with_fees as _sell_quote_fees)


def buy_quote_input_internal(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return asdict(_buy_quote(quote_amount_in, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, has_coin_creator))


def buy_quote_input_internal_with_fees(
    quote_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    return asdict(_buy_quote_fees(quote_amount_in, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, fee_basis_points))


def buy_base_input_internal(
    base_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return asdict(_buy_base(base_amount_out, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, has_coin_creator))


def buy_base_input_internal_with_fees(
    base_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    return asdict(_buy_base_fees(base_amount_out, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, fee_basis_points))


def sell_base_input_internal(
    base_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return asdict(_sell_base(base_amount_in, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, has_coin_creator))


def sell_base_input_internal_with_fees(
    base_amount_in: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    return asdict(_sell_base_fees(base_amount_in, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, fee_basis_points))


def sell_quote_input_internal(
    quote_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    has_coin_creator: bool,
) -> Dict[str, int]:
    return asdict(_sell_quote(quote_amount_out, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, has_coin_creator))


def sell_quote_input_internal_with_fees(
    quote_amount_out: int,
    slippage_basis_points: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
    fee_basis_points: PumpSwapFeeBasisPoints,
) -> Dict[str, int]:
    return asdict(_sell_quote_fees(quote_amount_out, slippage_basis_points, pool_base_reserves, pool_quote_reserves, virtual_quote_reserves, fee_basis_points))


def calculate_price_impact(
    amount_in: int,
    pool_base_reserves: int,
    pool_quote_reserves: int,
    virtual_quote_reserves: int,
) -> float:
    """Calculate price impact as a percentage"""
    if pool_base_reserves == 0 or pool_quote_reserves == 0:
        return 0.0
    effective_quote_reserve = effective_quote_reserves(
        pool_quote_reserves, virtual_quote_reserves
    )

    # Current price
    current_price = effective_quote_reserve / pool_base_reserves

    # Price after trade
    new_base_reserves = pool_base_reserves + amount_in
    new_quote_reserves = (pool_base_reserves * effective_quote_reserve) // new_base_reserves

    if new_base_reserves == 0:
        return 0.0

    new_price = new_quote_reserves / new_base_reserves

    # Price impact
    if current_price == 0:
        return 0.0

    price_impact = abs(new_price - current_price) / current_price * 100
    return price_impact
