"""
Calculation utilities for Sol Trade SDK
Implements all AMM formulas for PumpFun, PumpSwap, Bonk, and Raydium protocols.
Uses Python integers for arbitrary precision arithmetic.
"""

from typing import Tuple, NamedTuple, Optional
from dataclasses import dataclass


# ===== Constants =====

# PumpFun constants - 100% from Rust: src/instruction/utils/pumpfun.rs global_constants
PUMPFUN_FEE_BASIS_POINTS = 95   # Protocol fee
PUMPFUN_CREATOR_FEE = 30       # Creator fee

# PumpSwap constants - 100% from Rust: src/instruction/utils/pumpswap.rs accounts
PUMPSWAP_LP_FEE_BASIS_POINTS = 25          # 0.25%
PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS = 5     # 0.05%
PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS = 5 # 0.05%

# Bonk constants - 100% from Rust: src/instruction/utils/bonk.rs accounts
BONK_PROTOCOL_FEE_RATE = 25   # 0.25%
BONK_PLATFORM_FEE_RATE = 100  # 1%
BONK_SHARE_FEE_RATE = 0       # 0%
# Legacy aliases (deprecated)
BONK_FEE_NUMERATOR = 25
BONK_FEE_DENOMINATOR = 10000

# Raydium AMM V4 constants - 100% from Rust: src/instruction/utils/raydium_amm_v4.rs accounts
RAYDIUM_AMM_V4_FEE_NUMERATOR = 25
RAYDIUM_AMM_V4_FEE_DENOMINATOR = 10000  # 0.25%

# Raydium CPMM constants - 100% from Rust: src/instruction/utils/raydium_cpmm.rs accounts
RAYDIUM_CPMM_FEE_RATE_DENOMINATOR = 1_000_000
RAYDIUM_CPMM_TRADE_FEE_RATE = 2500
RAYDIUM_CPMM_CREATOR_FEE_RATE = 0
RAYDIUM_CPMM_PROTOCOL_FEE_RATE = 120000
RAYDIUM_CPMM_FUND_FEE_RATE = 40000

# Maximum slippage in basis points (99.99% = 9999 bps)
# This prevents the wrap amount from doubling when slippage is 100%
MAX_SLIPPAGE_BASIS_POINTS = 9999


# ===== Utility Functions =====

def compute_fee(amount: int, fee_basis_points: int, denominator: int = 10_000) -> int:
    """
    Calculate fee amount from basis points using ceiling division.
    
    100% from Rust: src/utils/calc/common.rs compute_fee
    
    Args:
        amount: The amount to calculate fee for
        fee_basis_points: Fee in basis points (1 bp = 0.01%)
    
    Returns:
        Fee amount using ceiling division
    """
    return ceil_div(amount * fee_basis_points, denominator)


def ceil_div(a: int, b: int) -> int:
    """Ceiling division"""
    return (a + b - 1) // b


def calculate_with_slippage_buy(amount: int, slippage_bps: int) -> int:
    """
    Calculate maximum acceptable output for a buy with slippage.
    Returns amount + (amount * slippage_bps / 10000)
    
    100% from Rust: src/utils/calc/common.rs calculate_with_slippage_buy
    
    Note: Basis points are clamped to MAX_SLIPPAGE_BASIS_POINTS (9999 = 99.99%)
    to prevent the amount from doubling when slippage_bps = 10000.
    """
    # Clamp basis points to max 9999 (99.99%) to prevent amount doubling at 100%
    bps = slippage_bps if slippage_bps <= MAX_SLIPPAGE_BASIS_POINTS else MAX_SLIPPAGE_BASIS_POINTS
    return amount + (amount * bps) // 10000


def calculate_with_slippage_sell(amount: int, slippage_bps: int) -> int:
    """
    Calculate minimum acceptable output for a sell with slippage.
    Returns amount - (amount * slippage_bps / 10000)
    
    100% from Rust: src/utils/calc/common.rs calculate_with_slippage_sell
    
    Note: Returns 1 if amount <= slippage_bps / 10000 to ensure minimum output.
    """
    # Rust: if amount <= basis_points / 10000 { 1 } else { ... }
    if amount <= slippage_bps // 10000:
        return 1
    return amount - (amount * slippage_bps) // 10000


# ===== PumpFun Calculations =====

def get_buy_token_amount_from_sol_amount(
    sol_amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
    real_token_reserves: int,
    has_creator: bool = False,
) -> int:
    """
    Calculate the amount of tokens received for a given SOL amount on PumpFun.
    
    100% from Rust: src/utils/calc/pumpfun.rs get_buy_token_amount_from_sol_amount
    
    Args:
        sol_amount: SOL amount in lamports
        virtual_sol_reserves: Virtual SOL reserves
        virtual_token_reserves: Virtual token reserves
        real_token_reserves: Real token reserves
        has_creator: Whether there is a creator (affects fee)
    """
    if sol_amount == 0 or virtual_token_reserves == 0:
        return 0

    # Calculate total fee basis points
    total_fee_basis_points = PUMPFUN_FEE_BASIS_POINTS
    if has_creator:
        total_fee_basis_points += PUMPFUN_CREATOR_FEE

    # Rust: input_amount = amount * 10000 / (total_fee + 10000)
    input_amount = (sol_amount * 10000) // (total_fee_basis_points + 10000)
    
    # Rust: denominator = virtual_sol_reserves + input_amount
    denominator = virtual_sol_reserves + input_amount
    
    # Rust: tokens_received = input_amount * virtual_token_reserves / denominator
    tokens_received = (input_amount * virtual_token_reserves) // denominator

    # Cap at real token reserves
    tokens_received = min(tokens_received, real_token_reserves)

    # Special handling for small amounts (matching Rust exactly)
    LAMPORTS_PER_SOL = 1_000_000_000
    if tokens_received <= 100 * 1_000_000:
        if sol_amount > LAMPORTS_PER_SOL // 100:  # > 0.01 SOL
            tokens_received = 25547619 * 1_000_000
        else:
            tokens_received = 255476 * 1_000_000

    return tokens_received


def get_sell_sol_amount_from_token_amount(
    token_amount: int,
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
    has_creator: bool = False,
    real_sol_reserves: Optional[int] = None,
) -> int:
    """
    Calculate the amount of SOL received for selling tokens on PumpFun.
    
    100% from Rust: src/utils/calc/pumpfun.rs get_sell_sol_amount_from_token_amount
    
    Args:
        token_amount: Token amount to sell
        virtual_sol_reserves: Virtual SOL reserves
        virtual_token_reserves: Virtual token reserves
        has_creator: Whether there is a creator (affects fee)
    """
    if token_amount == 0 or virtual_token_reserves == 0:
        return 0

    # Rust: numerator = amount * virtual_sol_reserves
    numerator = token_amount * virtual_sol_reserves
    
    # Rust: denominator = virtual_token_reserves + amount
    denominator = virtual_token_reserves + token_amount
    
    # Rust: sol_cost = numerator / denominator
    sol_cost = numerator // denominator

    # Calculate total fee basis points
    total_fee_basis_points = PUMPFUN_FEE_BASIS_POINTS
    if has_creator:
        total_fee_basis_points += PUMPFUN_CREATOR_FEE

    # Rust: fee = compute_fee(sol_cost, total_fee_basis_points)
    fee = compute_fee(sol_cost, total_fee_basis_points)

    # Rust: sol_cost.saturating_sub(fee)
    return max(0, sol_cost - fee)


# ===== PumpSwap Result Types =====
# 100% from Rust: src/utils/calc/pumpswap.rs

@dataclass
class BuyBaseInputResult:
    """Result of buy base input calculation - from Rust pumpswap.rs"""
    internal_quote_amount: int
    ui_quote: int
    max_quote: int

    @property
    def amount_out(self) -> int:
        return self.ui_quote

    @property
    def fee(self) -> int:
        return max(0, self.max_quote - self.ui_quote)


@dataclass
class BuyQuoteInputResult:
    """Result of buy quote input calculation - from Rust pumpswap.rs"""
    base: int
    internal_quote_without_fees: int
    max_quote: int


@dataclass
class SellBaseInputResult:
    """Result of sell base input calculation - from Rust pumpswap.rs"""
    ui_quote: int
    min_quote: int
    internal_quote_amount_out: int

    @property
    def amount_out(self) -> int:
        return self.ui_quote

    @property
    def fee(self) -> int:
        return max(0, self.internal_quote_amount_out - self.ui_quote)


@dataclass
class SellQuoteInputResult:
    """Result of sell quote input calculation - from Rust pumpswap.rs"""
    internal_raw_quote: int
    base: int
    min_quote: int


# ===== PumpSwap Calculations =====
# 100% from Rust: src/utils/calc/pumpswap.rs

def buy_base_input_internal(
    base: Optional[int] = None,
    slippage_basis_points: Optional[int] = None,
    base_reserve: Optional[int] = None,
    quote_reserve: Optional[int] = None,
    has_coin_creator: bool = False,
    **kwargs,
) -> BuyBaseInputResult:
    """
    Calculate quote needed to buy base tokens on PumpSwap.
    
    100% from Rust: src/utils/calc/pumpswap.rs buy_base_input_internal
    """
    if "amount_in" in kwargs:
        base = kwargs.pop("amount_in")
    if "reserve_in" in kwargs:
        base_reserve = kwargs.pop("reserve_in")
    if "reserve_out" in kwargs:
        quote_reserve = kwargs.pop("reserve_out")
    if "slippage_bps" in kwargs:
        slippage_basis_points = kwargs.pop("slippage_bps")
    if kwargs:
        unexpected = ", ".join(kwargs.keys())
        raise TypeError(f"unexpected keyword argument(s): {unexpected}")
    if base is None or slippage_basis_points is None or base_reserve is None or quote_reserve is None:
        raise TypeError("base, slippage_basis_points, base_reserve and quote_reserve are required")

    if base_reserve == 0 or quote_reserve == 0:
        return BuyBaseInputResult(0, 0, 0)
    if base > base_reserve:
        return BuyBaseInputResult(0, 0, 0)

    # Rust: quote_amount_in = ceil_div(quote_reserve * base, base_reserve - base)
    numerator = quote_reserve * base
    denominator = base_reserve - base
    if denominator == 0:
        return BuyBaseInputResult(0, 0, 0)
    
    quote_amount_in = ceil_div(numerator, denominator)

    # Calculate fees (Rust: compute_fee with LP_FEE, PROTOCOL_FEE, COIN_CREATOR_FEE)
    lp_fee = compute_fee(quote_amount_in, PUMPSWAP_LP_FEE_BASIS_POINTS)
    protocol_fee = compute_fee(quote_amount_in, PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS)
    coin_creator_fee = 0
    if has_coin_creator:
        coin_creator_fee = compute_fee(quote_amount_in, PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS)

    total_quote = quote_amount_in + lp_fee + protocol_fee + coin_creator_fee
    max_quote = calculate_with_slippage_buy(total_quote, slippage_basis_points)

    return BuyBaseInputResult(
        internal_quote_amount=quote_amount_in,
        ui_quote=total_quote,
        max_quote=max_quote,
    )


def buy_quote_input_internal(
    quote: int,
    slippage_basis_points: int,
    base_reserve: int,
    quote_reserve: int,
    has_coin_creator: bool = False,
) -> BuyQuoteInputResult:
    """
    Calculate base tokens received for quote input on PumpSwap.
    
    100% from Rust: src/utils/calc/pumpswap.rs buy_quote_input_internal
    """
    if base_reserve == 0 or quote_reserve == 0:
        return BuyQuoteInputResult(0, 0, 0)

    # Calculate total fee basis points
    total_fee_bps = PUMPSWAP_LP_FEE_BASIS_POINTS + PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS
    if has_coin_creator:
        total_fee_bps += PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS
    denominator = 10000 + total_fee_bps

    # Rust: effective_quote = quote * 10000 / denominator
    effective_quote = (quote * 10000) // denominator

    # Rust: base_amount_out = base_reserve * effective_quote / (quote_reserve + effective_quote)
    numerator = base_reserve * effective_quote
    denominator_effective = quote_reserve + effective_quote
    if denominator_effective == 0:
        return BuyQuoteInputResult(0, effective_quote, 0)

    base_amount_out = numerator // denominator_effective
    max_quote = calculate_with_slippage_buy(quote, slippage_basis_points)

    return BuyQuoteInputResult(
        base=base_amount_out,
        internal_quote_without_fees=effective_quote,
        max_quote=max_quote,
    )


def sell_base_input_internal(
    base: Optional[int] = None,
    slippage_basis_points: Optional[int] = None,
    base_reserve: Optional[int] = None,
    quote_reserve: Optional[int] = None,
    has_coin_creator: bool = False,
    **kwargs,
) -> SellBaseInputResult:
    """
    Calculate quote received for selling base tokens on PumpSwap.
    
    100% from Rust: src/utils/calc/pumpswap.rs sell_base_input_internal
    """
    if "amount_in" in kwargs:
        base = kwargs.pop("amount_in")
    if "reserve_in" in kwargs:
        base_reserve = kwargs.pop("reserve_in")
    if "reserve_out" in kwargs:
        quote_reserve = kwargs.pop("reserve_out")
    if "slippage_bps" in kwargs:
        slippage_basis_points = kwargs.pop("slippage_bps")
    if kwargs:
        unexpected = ", ".join(kwargs.keys())
        raise TypeError(f"unexpected keyword argument(s): {unexpected}")
    if base is None or slippage_basis_points is None or base_reserve is None or quote_reserve is None:
        raise TypeError("base, slippage_basis_points, base_reserve and quote_reserve are required")

    if base_reserve == 0 or quote_reserve == 0:
        return SellBaseInputResult(0, 0, 0)

    # Rust: quote_amount_out = (quote_reserve * base) / (base_reserve + base)
    numerator = quote_reserve * base
    denominator = base_reserve + base
    if denominator == 0:
        return SellBaseInputResult(0, 0, 0)
    
    quote_amount_out = numerator // denominator

    # Calculate fees
    lp_fee = compute_fee(quote_amount_out, PUMPSWAP_LP_FEE_BASIS_POINTS)
    protocol_fee = compute_fee(quote_amount_out, PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS)
    coin_creator_fee = 0
    if has_coin_creator:
        coin_creator_fee = compute_fee(quote_amount_out, PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS)

    total_fees = lp_fee + protocol_fee + coin_creator_fee
    if total_fees > quote_amount_out:
        return SellBaseInputResult(0, 0, quote_amount_out)
    
    final_quote = quote_amount_out - total_fees
    min_quote = calculate_with_slippage_sell(final_quote, slippage_basis_points)

    return SellBaseInputResult(
        ui_quote=final_quote,
        min_quote=min_quote,
        internal_quote_amount_out=quote_amount_out,
    )

def sell_quote_input_internal(
    quote: int,
    slippage_basis_points: int,
    base_reserve: int,
    quote_reserve: int,
    has_coin_creator: bool = False,
) -> SellQuoteInputResult:
    """
    Calculate base needed to receive quote amount on PumpSwap.
    
    100% from Rust: src/utils/calc/pumpswap.rs sell_quote_input_internal
    """
    if base_reserve == 0 or quote_reserve == 0:
        return SellQuoteInputResult(0, 0, 0)
    if quote > quote_reserve:
        return SellQuoteInputResult(0, 0, 0)

    # Calculate reverse fees
    coin_creator_fee_bps = PUMPSWAP_COIN_CREATOR_FEE_BASIS_POINTS if has_coin_creator else 0
    total_fee_bps = PUMPSWAP_LP_FEE_BASIS_POINTS + PUMPSWAP_PROTOCOL_FEE_BASIS_POINTS + coin_creator_fee_bps
    
    # Rust: raw_quote = ceil_div(quote * 10000, 10000 - total_fee_bps)
    denominator = 10000 - total_fee_bps
    if denominator == 0:
        return SellQuoteInputResult(0, 0, 0)
    
    raw_quote = ceil_div(quote * 10000, denominator)

    if raw_quote >= quote_reserve:
        return SellQuoteInputResult(raw_quote, 0, 0)

    # Rust: base_amount_in = ceil_div(base_reserve * raw_quote, quote_reserve - raw_quote)
    numerator = base_reserve * raw_quote
    denominator = quote_reserve - raw_quote
    if denominator == 0:
        return SellQuoteInputResult(raw_quote, 0, 0)
    
    base_amount_in = ceil_div(numerator, denominator)
    min_quote = calculate_with_slippage_sell(quote, slippage_basis_points)

    return SellQuoteInputResult(
        internal_raw_quote=raw_quote,
        base=base_amount_in,
        min_quote=min_quote,
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


def _compute_raydium_cpmm_trading_fee(amount: int, fee_rate: int) -> int:
    """Compute trading fee using ceiling division."""
    numerator = amount * fee_rate
    return (numerator + RAYDIUM_CPMM_FEE_RATE_DENOMINATOR - 1) // RAYDIUM_CPMM_FEE_RATE_DENOMINATOR


def _compute_raydium_cpmm_protocol_fund_fee(amount: int, fee_rate: int) -> int:
    """Compute protocol or fund fee using floor division."""
    numerator = amount * fee_rate
    return numerator // RAYDIUM_CPMM_FEE_RATE_DENOMINATOR


# ===== Raydium CPMM Calculations =====
# 100% from Rust: src/utils/calc/raydium_cpmm.rs


def raydium_cpmm_compute_swap_amount(
    base_reserve: int,
    quote_reserve: int,
    is_base_in: bool,
    amount_in: int,
    slippage_basis_points: int,
) -> dict:
    """
    Compute swap parameters for Raydium CPMM.
    
    100% from Rust: src/utils/calc/raydium_cpmm.rs compute_swap_amount
    
    Returns dict with:
        - all_trade: bool
        - amount_in: int
        - amount_out: int
        - min_amount_out: int
        - fee: int (trade_fee)
    """
    if base_reserve == 0 or quote_reserve == 0:
        return {"all_trade": False, "amount_in": 0, "amount_out": 0, "min_amount_out": 0, "fee": 0}
    
    input_reserve, output_reserve = (base_reserve, quote_reserve) if is_base_in else (quote_reserve, base_reserve)
    
    # Rust: swap_base_input with is_creator_fee_on_input = True
    trade_fee = _compute_raydium_cpmm_trading_fee(amount_in, RAYDIUM_CPMM_TRADE_FEE_RATE)
    
    # Creator fee is 0, so input_amount_less_fees = amount_in - trade_fee
    input_amount_less_fees = amount_in - trade_fee
    
    # Protocol and fund fees (calculated from trade_fee)
    protocol_fee = _compute_raydium_cpmm_protocol_fund_fee(trade_fee, RAYDIUM_CPMM_PROTOCOL_FEE_RATE)
    fund_fee = _compute_raydium_cpmm_protocol_fund_fee(trade_fee, RAYDIUM_CPMM_FUND_FEE_RATE)
    
    # Constant product formula
    output_amount_swapped = (output_reserve * input_amount_less_fees) // (input_reserve + input_amount_less_fees)
    
    # Creator fee is 0, so output_amount = output_amount_swapped
    output_amount = output_amount_swapped
    
    # Apply slippage
    min_amount_out = int(output_amount * (1.0 - slippage_basis_points / 10000.0))
    
    return {
        "all_trade": True,
        "amount_in": amount_in,
        "amount_out": output_amount,
        "min_amount_out": min_amount_out,
        "fee": trade_fee,
    }


def raydium_cpmm_get_amount_out(
    amount_in: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate output amount for Raydium CPMM.
    
    Simplified version - for full calculation use raydium_cpmm_compute_swap_amount.
    """
    if amount_in == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    # Apply trade fee using ceiling division
    trade_fee = _compute_raydium_cpmm_trading_fee(amount_in, RAYDIUM_CPMM_TRADE_FEE_RATE)
    amount_in_less_fee = amount_in - trade_fee

    # Calculate output
    numerator = amount_in_less_fee * reserve_out
    denominator = reserve_in + amount_in_less_fee
    
    return numerator // denominator


def raydium_cpmm_get_amount_in(
    amount_out: int,
    reserve_in: int,
    reserve_out: int,
) -> int:
    """
    Calculate input amount for Raydium CPMM.
    
    Simplified version - for full calculation use raydium_cpmm_compute_swap_amount.
    """
    if amount_out == 0 or reserve_in == 0 or reserve_out == 0:
        return 0

    if amount_out >= reserve_out:
        return 0

    # Calculate required input (reverse constant product)
    numerator = reserve_in * amount_out
    denominator = reserve_out - amount_out
    amount_in_needed = ceil_div(numerator, denominator)
    
    # Add trade fee
    # amount_in = amount_in_needed / (1 - trade_fee_rate/fee_denominator)
    # Using ceiling division
    amount_in = ceil_div(
        amount_in_needed * RAYDIUM_CPMM_FEE_RATE_DENOMINATOR,
        RAYDIUM_CPMM_FEE_RATE_DENOMINATOR - RAYDIUM_CPMM_TRADE_FEE_RATE
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


# ===== Price Calculation Functions =====
# 100% port from Rust: src/utils/price/*

# Constants for decimals
DEFAULT_TOKEN_DECIMALS = 6
SOL_DECIMALS = 9
LAMPORTS_PER_SOL = 1_000_000_000
SCALE = 1_000_000_000  # PumpFun scale factor


def price_token_in_sol(
    virtual_sol_reserves: int,
    virtual_token_reserves: int,
) -> float:
    """
    Calculate the token price in SOL based on virtual reserves.
    
    100% from Rust: src/utils/price/pumpfun.rs price_token_in_sol
    
    Args:
        virtual_sol_reserves: Virtual SOL reserves in the bonding curve
        virtual_token_reserves: Virtual token reserves in the bonding curve
    
    Returns:
        Token price in SOL as f64
    """
    v_sol = virtual_sol_reserves / LAMPORTS_PER_SOL
    v_tokens = virtual_token_reserves / SCALE
    if v_tokens == 0.0:
        return 0.0
    return v_sol / v_tokens


def price_token_in_wsol(
    virtual_base: int,
    virtual_quote: int,
    real_base: int,
    real_quote: int,
) -> float:
    """
    Calculate the price of token in WSOL.
    
    100% from Rust: src/utils/price/bonk.rs price_token_in_wsol
    
    Args:
        virtual_base: Virtual base reserves
        virtual_quote: Virtual quote reserves
        real_base: Real base reserves
        real_quote: Real quote reserves
    
    Returns:
        The price of token in WSOL
    """
    return price_base_in_quote_with_virtual(
        virtual_base,
        virtual_quote,
        real_base,
        real_quote,
        DEFAULT_TOKEN_DECIMALS,
        SOL_DECIMALS,
    )


def price_base_in_quote_with_virtual(
    virtual_base: int,
    virtual_quote: int,
    real_base: int,
    real_quote: int,
    base_decimals: int = DEFAULT_TOKEN_DECIMALS,
    quote_decimals: int = SOL_DECIMALS,
) -> float:
    """
    Calculate the price of base in quote using virtual and real reserves.
    
    100% from Rust: src/utils/price/bonk.rs price_base_in_quote
    
    Args:
        virtual_base: Virtual base reserves
        virtual_quote: Virtual quote reserves
        real_base: Real base reserves
        real_quote: Real quote reserves
        base_decimals: Base decimals
        quote_decimals: Quote decimals
    
    Returns:
        The price of base in quote
    """
    # Calculate decimal places difference
    decimal_diff = quote_decimals - base_decimals
    if decimal_diff >= 0:
        decimal_factor = 10.0 ** decimal_diff
    else:
        decimal_factor = 1.0 / (10.0 ** (-decimal_diff))
    
    # Calculate reserves state before price calculation
    quote_reserves = virtual_quote + real_quote if virtual_quote and real_quote else virtual_quote
    base_reserves = virtual_base - real_base if virtual_base > real_base else virtual_base

    if base_reserves == 0:
        return 0.0

    if decimal_factor == 0.0:
        return 0.0

    # Use floating point calculation to avoid precision loss from integer division
    price = (quote_reserves) / (base_reserves) / decimal_factor

    return price


def price_base_in_quote(
    base_reserve: int,
    quote_reserve: int,
    base_decimals: int = DEFAULT_TOKEN_DECIMALS,
    quote_decimals: int = SOL_DECIMALS,
) -> float:
    """
    Calculate the token price in quote based on base and quote reserves.
    
    100% from Rust: src/utils/price/common.rs price_base_in_quote
    
    Args:
        base_reserve: Base reserve in the pool
        quote_reserve: Quote reserve in the pool
        base_decimals: Base decimals
        quote_decimals: Quote decimals
    
    Returns:
        Token price in quote as f64
    """
    base = base_reserve / (10.0 ** base_decimals)
    quote = quote_reserve / (10.0 ** quote_decimals)
    if base == 0.0:
        return 0.0
    return quote / base


def price_quote_in_base(
    base_reserve: int,
    quote_reserve: int,
    base_decimals: int = DEFAULT_TOKEN_DECIMALS,
    quote_decimals: int = SOL_DECIMALS,
) -> float:
    """
    Calculate the token price in base based on base and quote reserves.
    
    100% from Rust: src/utils/price/common.rs price_quote_in_base
    
    Args:
        base_reserve: Base reserve in the pool
        quote_reserve: Quote reserve in the pool
        base_decimals: Base decimals
        quote_decimals: Quote decimals
    
    Returns:
        Token price in base as f64
    """
    base = base_reserve / (10.0 ** base_decimals)
    quote = quote_reserve / (10.0 ** quote_decimals)
    if quote == 0.0:
        return 0.0
    return base / quote


def price_base_in_quote_from_reserves(
    base_reserve: int,
    quote_reserve: int,
    base_decimals: int = DEFAULT_TOKEN_DECIMALS,
    quote_decimals: int = SOL_DECIMALS,
) -> float:
    """
    Alias for price_base_in_quote - for Raydium CPMM/AMM V4 compatibility.
    
    100% from Rust: src/utils/price/raydium_cpmm.rs / raydium_amm_v4.rs
    """
    return price_base_in_quote(base_reserve, quote_reserve, base_decimals, quote_decimals)


def price_quote_in_base_from_reserves(
    base_reserve: int,
    quote_reserve: int,
    base_decimals: int = DEFAULT_TOKEN_DECIMALS,
    quote_decimals: int = SOL_DECIMALS,
) -> float:
    """
    Alias for price_quote_in_base - for Raydium CPMM/AMM V4 compatibility.
    
    100% from Rust: src/utils/price/raydium_cpmm.rs / raydium_amm_v4.rs
    """
    return price_quote_in_base(base_reserve, quote_reserve, base_decimals, quote_decimals)


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


# ===== Raydium CLMM Price Calculations - from Rust: src/utils/price/raydium_clmm.rs =====

def price_token0_in_token1(
    sqrt_price_x64: int,
    decimals_token0: int,
    decimals_token1: int,
) -> float:
    """
    Calculate the price of token0 in token1 from sqrt price.
    
    100% from Rust: src/utils/price/raydium_clmm.rs price_token0_in_token1
    
    Args:
        sqrt_price_x64: The sqrt price of the pool in Q64.64 format
        decimals_token0: The decimals of token0
        decimals_token1: The decimals of token1
    
    Returns:
        The price of token0 in token1
    """
    sqrt_price = sqrt_price_x64 / (2 ** 64)  # Q64.64 to float
    price_raw = sqrt_price * sqrt_price  # Price without decimal adjustment
    scale = 10 ** (decimals_token0 - decimals_token1)
    return price_raw * scale


def price_token1_in_token0(
    sqrt_price_x64: int,
    decimals_token0: int,
    decimals_token1: int,
) -> float:
    """
    Calculate the price of token1 in token0 from sqrt price.
    
    100% from Rust: src/utils/price/raydium_clmm.rs price_token1_in_token0
    
    Args:
        sqrt_price_x64: The sqrt price of the pool in Q64.64 format
        decimals_token0: The decimals of token0
        decimals_token1: The decimals of token1
    
    Returns:
        The price of token1 in token0
    """
    if sqrt_price_x64 == 0:
        return 0.0
    return 1.0 / price_token0_in_token1(sqrt_price_x64, decimals_token0, decimals_token1)
