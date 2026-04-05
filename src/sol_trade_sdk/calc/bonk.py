"""
Bonk calculation utilities.
Based on sol-trade-sdk Rust implementation.
"""

from typing import Dict

# Fee rates (basis points)
PROTOCOL_FEE_RATE = 100  # 1%
PLATFORM_FEE_RATE = 50   # 0.5%
SHARE_FEE_RATE = 25      # 0.25%

# Default virtual reserves
DEFAULT_VIRTUAL_BASE = 1073025605596382
DEFAULT_VIRTUAL_QUOTE = 30000852951


def get_amount_in(
    amount_out: int,
    protocol_fee_rate: int,
    platform_fee_rate: int,
    share_fee_rate: int,
    virtual_base: int,
    virtual_quote: int,
    real_base_before: int,
    real_quote_before: int,
    real_base_after: int,
) -> int:
    """
    Calculate input amount needed for desired output.
    Used when exact output is specified.
    """
    if amount_out == 0:
        return 0

    # Total fee rate
    total_fee_rate = protocol_fee_rate + platform_fee_rate + share_fee_rate

    # Calculate using constant product formula
    # k = virtual_base * virtual_quote
    k = virtual_base * virtual_quote

    # new_virtual_base = virtual_base - amount_out
    new_virtual_base = virtual_base - amount_out

    if new_virtual_base == 0:
        return 0

    # new_virtual_quote = k / new_virtual_base
    new_virtual_quote = k // new_virtual_base

    # quote_in = new_virtual_quote - virtual_quote
    quote_in = new_virtual_quote - virtual_quote

    # Add fees
    amount_in = quote_in * 10000 // (10000 - total_fee_rate)

    return amount_in


def get_amount_out(
    amount_in: int,
    protocol_fee_rate: int,
    platform_fee_rate: int,
    share_fee_rate: int,
    virtual_base: int,
    virtual_quote: int,
    real_base_before: int,
    real_quote_before: int,
    real_quote_after: int,
) -> int:
    """
    Calculate output amount for given input.
    """
    if amount_in == 0:
        return 0

    # Total fee rate
    total_fee_rate = protocol_fee_rate + platform_fee_rate + share_fee_rate

    # Calculate fee
    fee = amount_in * total_fee_rate // 10000
    amount_in_after_fee = amount_in - fee

    # k = virtual_base * virtual_quote
    k = virtual_base * virtual_quote

    # new_virtual_quote = virtual_quote + amount_in_after_fee
    new_virtual_quote = virtual_quote + amount_in_after_fee

    # new_virtual_base = k / new_virtual_quote
    if new_virtual_quote == 0:
        return 0

    new_virtual_base = k // new_virtual_quote

    # base_out = virtual_base - new_virtual_base
    base_out = virtual_base - new_virtual_base

    return base_out


def get_amount_in_net(
    amount_in: int,
    protocol_fee_rate: int,
    platform_fee_rate: int,
    share_fee_rate: int,
) -> int:
    """
    Calculate net input after fees.
    """
    total_fee_rate = protocol_fee_rate + platform_fee_rate + share_fee_rate
    fee = amount_in * total_fee_rate // 10000
    return amount_in - fee


def compute_swap_amount(
    amount_in: int,
    slippage_basis_points: int,
    virtual_base: int,
    virtual_quote: int,
    is_buy: bool,
) -> Dict[str, int]:
    """
    Compute swap amount with slippage.
    Returns dict with 'amount_out' and 'min_amount_out'.
    """
    if is_buy:
        # Buying base with quote
        amount_out = get_amount_out(
            amount_in,
            PROTOCOL_FEE_RATE,
            PLATFORM_FEE_RATE,
            SHARE_FEE_RATE,
            virtual_base,
            virtual_quote,
            0, 0, 0,
        )
    else:
        # Selling base for quote
        amount_out = get_amount_in(
            amount_in,
            PROTOCOL_FEE_RATE,
            PLATFORM_FEE_RATE,
            SHARE_FEE_RATE,
            virtual_base,
            virtual_quote,
            0, 0, 0,
        )

    # Apply slippage
    min_amount_out = amount_out - (amount_out * slippage_basis_points // 10_000)

    return {
        "amount_out": amount_out,
        "min_amount_out": min_amount_out,
    }
