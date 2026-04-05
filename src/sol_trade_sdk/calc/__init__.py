"""
Calculation utilities for Sol Trade SDK
Implements all AMM formulas for PumpFun, PumpSwap, Bonk, and Raydium protocols.
Uses Python integers for arbitrary precision arithmetic.
"""

from typing import Tuple, NamedTuple
from dataclasses import dataclass


# ===== Constants =====

# PumpFun constants
PUMPFUN_FEE_BASIS_POINTS = 100  # 1%
PUMPFUN_CREATOR_FEE = 50  # 0.5%

# PumpSwap constants
PUMPSWAP_LP_FEE_BASIS_POINTS = 25  # 0.25%
PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS = 5  # 0.05%
PUMPSWAP_TOTAL_FEE_BASIS_POINTS = 30  # 0.30%
PUMPSWAP_CURVE_FEE_BASIS_POINTS = 100  # 1%

# Bonk constants
BONK_FEE_NUMERATOR = 25
BONK_FEE_DENOMINATOR = 10000

# Raydium constants
RAYDIUM_AMM_V4_FEE_NUMERATOR = 25
RAYDIUM_AMM_V4_FEE_DENOMINATOR = 10000  # 0.25%
RAYDIUM_CPMM_FEE_NUMERATOR = 30
RAYDIUM_CPMM_FEE_DENOMINATOR = 10000  # 0.30%


# ===== Utility Functions =====

def compute_fee(amount: int, fee_numerator: int, fee_denominator: int) -> int:
    """Calculate fee amount from basis points"""
    return (amount * fee_numerator) // fee_denominator


def ceil_div(a: int, b: int) -> int:
    """Ceiling division"""
    return (a + b - 1) // b


def calculate_with_slippage_buy(amount: int, slippage_bps: int) -> int:
    """
    Calculate maximum acceptable output for a buy with slippage.
    Returns amount * (10000 + slippage_bps) / 10000
    """
    return (amount * (10000 + slippage_bps)) // 10000


def calculate_with_slippage_sell(amount: int, slippage_bps: int) -> int:
    """
    Calculate minimum acceptable output for a sell with slippage.
    Returns amount * (10000 - slippage_bps) / 10000
    """
    return (amount * (10000 - slippage_bps)) // 10000


# ===== PumpFun Calculations =====

def get_buy_token_amount_from_sol_amount(
    sol_amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
    real_token_reserves: int,
) -> int:
    """
    Calculate the amount of tokens received for a given SOL amount on PumpFun.
    
    Uses constant product formula:
    k = virtual_sol * virtual_tokens
    new_virtual_sol = virtual_sol + sol_in
    new_virtual_tokens = k / new_virtual_sol
    tokens_out = virtual_tokens - new_virtual_tokens
    """
    if sol_amount == 0 or virtual_sol_reserves == 0 or virtual_token_reserves == 0:
        return 0

    # k = virtual_sol * virtual_tokens
    k = virtual_sol_reserves * virtual_token_reserves
    
    # new_virtual_sol = virtual_sol + sol_in
    new_virtual_sol = virtual_sol_reserves + sol_amount
    
    # new_virtual_tokens = k / new_virtual_sol
    new_virtual_tokens = k // new_virtual_sol
    
    # tokens_out = virtual_tokens - new_virtual_tokens
    tokens_out = virtual_token_reserves - new_virtual_tokens
    
    # Apply fee deduction (1%)
    fee = (tokens_out * PUMPFUN_FEE_BASIS_POINTS) // 10000
    tokens_out_after_fee = tokens_out - fee
    
    # Cap at real token reserves
    if tokens_out_after_fee > real_token_reserves:
        return real_token_reserves
    
    return tokens_out_after_fee


def get_sell_sol_amount_from_token_amount(
    token_amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
    real_sol_reserves: int,
) -> int:
    """
    Calculate the amount of SOL received for selling tokens on PumpFun.
    
    Uses constant product formula:
    k = virtual_sol * virtual_tokens
    new_virtual_tokens = virtual_tokens + tokens_in
    new_virtual_sol = k / new_virtual_tokens
    sol_out = virtual_sol - new_virtual_sol
    """
    if token_amount == 0 or virtual_sol_reserves == 0 or virtual_token_reserves == 0:
        return 0

    # k = virtual_sol * virtual_tokens
    k = virtual_sol_reserves * virtual_token_reserves
    
    # new_virtual_tokens = virtual_tokens + tokens_in
    new_virtual_tokens = virtual_token_reserves + token_amount
    
    # new_virtual_sol = k / new_virtual_tokens
    new_virtual_sol = k // new_virtual_tokens
    
    # sol_out = virtual_sol - new_virtual_sol
    sol_out = virtual_sol_reserves - new_virtual_sol
    
    # Apply fee deduction (1%)
    fee = (sol_out * PUMPFUN_FEE_BASIS_POINTS) // 10000
    sol_out_after_fee = sol_out - fee
    
    # Cap at real sol reserves
    if sol_out_after_fee > real_sol_reserves:
        return real_sol_reserves
    
    return sol_out_after_fee


# ===== PumpSwap Result Types =====

@dataclass
class BuyBaseInputResult:
    """Result of buy base input calculation"""
    amount_out: int
    fee: int
    lp_fee: int
    protocol_fee: int
    curve_fee: int
    amount_in_after_curve_fee: int
    minimum_amount_out: int


@dataclass
class BuyQuoteInputResult:
    """Result of buy quote input calculation"""
    amount_in: int
    fee: int
    lp_fee: int
    protocol_fee: int
    curve_fee: int
    amount_in_after_curve_fee: int


@dataclass
class SellBaseInputResult:
    """Result of sell base input calculation"""
    amount_out: int
    fee: int
    lp_fee: int
    protocol_fee: int
    curve_fee: int
    minimum_amount_out: int


@dataclass
class SellQuoteInputResult:
    """Result of sell quote input calculation"""
    amount_in: int
    fee: int
    lp_fee: int
    protocol_fee: int
    curve_fee: int


# ===== PumpSwap Calculations =====

def buy_base_input_internal(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    slippage_bps: int = 500,
) -> BuyBaseInputResult:
    """
    Calculate buy output when inputting base token (SOL).
    
    Args:
        amount_in: Amount of SOL to spend
        reserve_in: SOL reserves in the pool
        reserve_out: Token reserves in the pool
        slippage_bps: Slippage tolerance in basis points
    
    Returns:
        BuyBaseInputResult with output amount and fee breakdown
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return BuyBaseInputResult(0, 0, 0, 0, 0, 0, 0)

    # Calculate curve fee (1%)
    curve_fee = (amount_in * PUMPSWAP_CURVE_FEE_BASIS_POINTS) // 10000
    amount_in_after_curve_fee = amount_in - curve_fee

    # Calculate total fee on the remaining amount
    total_fee = (amount_in_after_curve_fee * PUMPSWAP_TOTAL_FEE_BASIS_POINTS) // 10000
    
    # Split fees
    lp_fee = (amount_in_after_curve_fee * PUMPSWAP_LP_FEE_BASIS_POINTS) // 10000
    protocol_fee = (amount_in_after_curve_fee * PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS) // 10000

    # Apply fee to amount
    amount_in_with_fee = amount_in_after_curve_fee - total_fee

    # Calculate output using constant product: (r_in + a_in) * (r_out - a_out) = r_in * r_out
    # a_out = r_out - (r_in * r_out) / (r_in + a_in)
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    amount_out = numerator // denominator

    # Calculate minimum amount out with slippage
    minimum_amount_out = (amount_out * (10000 - slippage_bps)) // 10000

    return BuyBaseInputResult(
        amount_out=amount_out,
        fee=total_fee,
        lp_fee=lp_fee,
        protocol_fee=protocol_fee,
        curve_fee=curve_fee,
        amount_in_after_curve_fee=amount_in_after_curve_fee,
        minimum_amount_out=minimum_amount_out,
    )


def buy_quote_input_internal(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> BuyQuoteInputResult:
    """
    Calculate buy input when specifying desired output tokens.
    
    Args:
        amount_out: Amount of tokens desired
        reserve_in: SOL reserves in the pool
        reserve_out: Token reserves in the pool
    
    Returns:
        BuyQuoteInputResult with required input amount and fee breakdown
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return BuyQuoteInputResult(0, 0, 0, 0, 0, 0)

    # Calculate required input before fees
    # amount_in = (r_in * a_out) / (r_out - a_out)
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    if denominator <= 0:
        return BuyQuoteInputResult(0, 0, 0, 0, 0, 0)
    
    amount_in_before_fees = ceil_div(numerator, denominator)

    # Add total fees (0.30%)
    # amount_in = amount_in_before_fees / (1 - 0.003)
    amount_in_after_curve_fee = ceil_div(
        amount_in_before_fees * 10000,
        10000 - PUMPSWAP_TOTAL_FEE_BASIS_POINTS
    )

    # Add curve fee (1%)
    # amount_in = amount_in_after_curve_fee / (1 - 0.01)
    amount_in = ceil_div(
        amount_in_after_curve_fee * 10000,
        10000 - PUMPSWAP_CURVE_FEE_BASIS_POINTS
    )

    # Calculate fees
    curve_fee = amount_in - amount_in_after_curve_fee
    total_fee = amount_in_after_curve_fee - amount_in_before_fees
    lp_fee = (amount_in_after_curve_fee * PUMPSWAP_LP_FEE_BASIS_POINTS) // 10000
    protocol_fee = (amount_in_after_curve_fee * PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS) // 10000

    return BuyQuoteInputResult(
        amount_in=amount_in,
        fee=total_fee,
        lp_fee=lp_fee,
        protocol_fee=protocol_fee,
        curve_fee=curve_fee,
        amount_in_after_curve_fee=amount_in_after_curve_fee,
    )


def sell_base_input_internal(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
    slippage_bps: int = 500,
) -> SellBaseInputResult:
    """
    Calculate sell output when inputting tokens.
    
    Args:
        amount_in: Amount of tokens to sell
        reserve_in: Token reserves in the pool
        reserve_out: SOL reserves in the pool
        slippage_bps: Slippage tolerance in basis points
    
    Returns:
        SellBaseInputResult with output amount and fee breakdown
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return SellBaseInputResult(0, 0, 0, 0, 0, 0)

    # Calculate curve fee (1%)
    curve_fee = (amount_in * PUMPSWAP_CURVE_FEE_BASIS_POINTS) // 10000
    amount_in_after_curve_fee = amount_in - curve_fee

    # Calculate total fee on the remaining amount
    total_fee = (amount_in_after_curve_fee * PUMPSWAP_TOTAL_FEE_BASIS_POINTS) // 10000
    
    # Split fees
    lp_fee = (amount_in_after_curve_fee * PUMPSWAP_LP_FEE_BASIS_POINTS) // 10000
    protocol_fee = (amount_in_after_curve_fee * PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS) // 10000

    # Apply fee to amount
    amount_in_with_fee = amount_in_after_curve_fee - total_fee

    # Calculate output using constant product
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    amount_out = numerator // denominator

    # Calculate minimum amount out with slippage
    minimum_amount_out = (amount_out * (10000 - slippage_bps)) // 10000

    return SellBaseInputResult(
        amount_out=amount_out,
        fee=total_fee,
        lp_fee=lp_fee,
        protocol_fee=protocol_fee,
        curve_fee=curve_fee,
        minimum_amount_out=minimum_amount_out,
    )


def sell_quote_input_internal(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> SellQuoteInputResult:
    """
    Calculate sell input when specifying desired SOL output.
    
    Args:
        amount_out: Amount of SOL desired
        reserve_in: Token reserves in the pool
        reserve_out: SOL reserves in the pool
    
    Returns:
        SellQuoteInputResult with required input amount and fee breakdown
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return SellQuoteInputResult(0, 0, 0, 0, 0, 0)

    # Calculate required input before fees
    # amount_in = (r_in * a_out) / (r_out - a_out)
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    if denominator <= 0:
        return SellQuoteInputResult(0, 0, 0, 0, 0, 0)
    
    amount_in_before_fees = ceil_div(numerator, denominator)

    # Add total fees (0.30%)
    amount_in_after_curve_fee = ceil_div(
        amount_in_before_fees * 10000,
        10000 - PUMPSWAP_TOTAL_FEE_BASIS_POINTS
    )

    # Add curve fee (1%)
    amount_in = ceil_div(
        amount_in_after_curve_fee * 10000,
        10000 - PUMPSWAP_CURVE_FEE_BASIS_POINTS
    )

    # Calculate fees
    curve_fee = amount_in - amount_in_after_curve_fee
    total_fee = amount_in_after_curve_fee - amount_in_before_fees
    lp_fee = (amount_in_after_curve_fee * PUMPSWAP_LP_FEE_BASIS_POINTS) // 10000
    protocol_fee = (amount_in_after_curve_fee * PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS) // 10000

    return SellQuoteInputResult(
        amount_in=amount_in,
        fee=total_fee,
        lp_fee=lp_fee,
        protocol_fee=protocol_fee,
        curve_fee=curve_fee,
    )


# ===== Bonk Calculations =====

def get_bonk_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate output amount for Bonk AMM.
    
    Uses constant product formula with 0.25% fee.
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    # Apply fee
    amount_in_with_fee = amount_in * (BONK_FEE_DENOMINATOR - BONK_FEE_NUMERATOR)
    amount_in_with_fee = amount_in_with_fee // BONK_FEE_DENOMINATOR

    # Calculate output
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    
    return numerator // denominator


def get_bonk_amount_in(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate input amount for Bonk AMM.
    
    Uses constant product formula with 0.25% fee.
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    if amount_out >= reserve_out:
        return 0

    # Calculate required input
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    amount_in = ceil_div(numerator, denominator)

    # Add fee
    amount_in = ceil_div(
        amount_in * BONK_FEE_DENOMINATOR,
        BONK_FEE_DENOMINATOR - BONK_FEE_NUMERATOR
    )

    return amount_in


# ===== Raydium CPMM Calculations =====

def raydium_cpmm_get_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate output amount for Raydium CPMM.
    
    Uses constant product formula with 0.30% fee.
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    # Apply fee
    amount_in_with_fee = amount_in * (RAYDIUM_CPMM_FEE_DENOMINATOR - RAYDIUM_CPMM_FEE_NUMERATOR)
    amount_in_with_fee = amount_in_with_fee // RAYDIUM_CPMM_FEE_DENOMINATOR

    # Calculate output
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    
    return numerator // denominator


def raydium_cpmm_get_amount_in(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate input amount for Raydium CPMM.
    
    Uses constant product formula with 0.30% fee.
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    if amount_out >= reserve_out:
        return 0

    # Calculate required input
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    amount_in = ceil_div(numerator, denominator)

    # Add fee
    amount_in = ceil_div(
        amount_in * RAYDIUM_CPMM_FEE_DENOMINATOR,
        RAYDIUM_CPMM_FEE_DENOMINATOR - RAYDIUM_CPMM_FEE_NUMERATOR
    )

    return amount_in


# ===== Raydium AMM V4 Calculations =====

def raydium_amm_v4_get_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate output amount for Raydium AMM V4.
    
    Uses constant product formula with 0.25% fee.
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    # Apply fee
    amount_in_with_fee = amount_in * (RAYDIUM_AMM_V4_FEE_DENOMINATOR - RAYDIUM_AMM_V4_FEE_NUMERATOR)
    amount_in_with_fee = amount_in_with_fee // RAYDIUM_AMM_V4_FEE_DENOMINATOR

    # Calculate output
    numerator = amount_in_with_fee * reserve_out
    denominator = reserve_in + amount_in_with_fee
    
    return numerator // denominator


def raydium_amm_v4_get_amount_in(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate input amount for Raydium AMM V4.
    
    Uses constant product formula with 0.25% fee.
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    if amount_out >= reserve_out:
        return 0

    # Calculate required input
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    amount_in = ceil_div(numerator, denominator)

    # Add fee
    amount_in = ceil_div(
        amount_in * RAYDIUM_AMM_V4_FEE_DENOMINATOR,
        RAYDIUM_AMM_V4_FEE_DENOMINATOR - RAYDIUM_AMM_V4_FEE_NUMERATOR
    )

    return amount_in


# ===== Helper Functions =====

def calculate_price_impact(
    amount_in: int,
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> float:
    """
    Calculate the price impact of a trade.
    
    Returns the percentage price impact (e.g., 0.5 for 0.5%).
    """
    if reserve_in == 0 or reserve_out == 0:
        return 0.0

    # Mid price before trade
    mid_price_before = reserve_out / reserve_in

    # Execution price
    if amount_in == 0:
        return 0.0
    execution_price = amount_out / amount_in

    # Price impact
    if mid_price_before == 0:
        return 0.0
    price_impact = abs(mid_price_before - execution_price) / mid_price_before

    return price_impact * 100


def calculate_price(
    token_a_reserve: int,
    token_b_reserve: int,
    decimals_a: int = 9,
    decimals_b: int = 6,
) -> float:
    """
    Calculate the price of token A in terms of token B.
    
    Returns price of 1 token A in token B units.
    """
    if token_a_reserve == 0:
        return 0.0

    # Adjust for decimals
    adj_a = token_a_reserve / (10 ** decimals_a)
    adj_b = token_b_reserve / (10 ** decimals_b)

    return adj_b / adj_a


def lamports_to_sol(lamports: int) -> float:
    """Convert lamports to SOL"""
    return lamports / 1_000_000_000


def sol_to_lamports(sol: float) -> int:
    """Convert SOL to lamports"""
    return int(sol * 1_000_000_000)


def tokens_to_ui_amount(amount: int, decimals: int) -> float:
    """Convert raw token amount to UI amount"""
    return amount / (10 ** decimals)


def ui_amount_to_tokens(ui_amount: float, decimals: int) -> int:
    """Convert UI amount to raw token amount"""
    return int(ui_amount * (10 ** decimals))
