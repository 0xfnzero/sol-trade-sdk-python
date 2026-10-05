"""
Bonk calculation utilities.
100% from Rust: src/utils/calc/bonk.rs + src/instruction/utils/bonk.rs accounts
"""

from typing import Dict

# Fee rates (basis points) - 100% from Rust: src/instruction/utils/bonk.rs accounts
PROTOCOL_FEE_RATE = 25   # 0.25%
PLATFORM_FEE_RATE = 100  # 1%
SHARE_FEE_RATE = 0       # 0%

# Default virtual reserves
DEFAULT_VIRTUAL_BASE = 1073025605596382
DEFAULT_VIRTUAL_QUOTE = 30000852951

MAX_SLIPPAGE_BASIS_POINTS = 9999


def clamp_slippage_basis_points(basis_points: int) -> int:
    """Clamp slippage to MAX_SLIPPAGE_BASIS_POINTS (9999 = 99.99%)."""
    if basis_points > MAX_SLIPPAGE_BASIS_POINTS:
        return MAX_SLIPPAGE_BASIS_POINTS
    if basis_points < 0:
        return 0
    return basis_points


def get_buy_token_amount_from_sol_amount(
    amount_in: int,
    virtual_base: int,
    virtual_quote: int,
    real_base: int,
    real_quote: int,
    slippage_basis_points: int,
) -> int:
    """
    Calculate min tokens received when buying with SOL.
    100% from Rust: get_buy_token_amount_from_sol_amount
    """
    bps = clamp_slippage_basis_points(slippage_basis_points)
    protocol_fee = (amount_in * PROTOCOL_FEE_RATE) // 10000
    platform_fee = (amount_in * PLATFORM_FEE_RATE) // 10000
    share_fee = (amount_in * SHARE_FEE_RATE) // 10000
    amount_in_net = amount_in - protocol_fee - platform_fee - share_fee

    input_reserve = virtual_quote + real_quote
    output_reserve = virtual_base - real_base
    denominator = input_reserve + amount_in_net
    if denominator == 0:
        return 0
    amount_out = (amount_in_net * output_reserve) // denominator
    amount_out = amount_out - (amount_out * bps) // 10000
    return amount_out


def get_sell_sol_amount_from_token_amount(
    amount_in: int,
    virtual_base: int,
    virtual_quote: int,
    real_base: int,
    real_quote: int,
    slippage_basis_points: int,
) -> int:
    """
    Calculate min SOL received when selling tokens.
    100% from Rust: get_sell_sol_amount_from_token_amount
    """
    bps = clamp_slippage_basis_points(slippage_basis_points)
    input_reserve = virtual_base - real_base
    output_reserve = virtual_quote + real_quote
    denominator = input_reserve + amount_in
    if denominator == 0:
        return 0
    sol_amount_out = (amount_in * output_reserve) // denominator

    protocol_fee = (sol_amount_out * PROTOCOL_FEE_RATE) // 10000
    platform_fee = (sol_amount_out * PLATFORM_FEE_RATE) // 10000
    share_fee = (sol_amount_out * SHARE_FEE_RATE) // 10000
    sol_amount_net = sol_amount_out - protocol_fee - platform_fee - share_fee
    return sol_amount_net - (sol_amount_net * bps) // 10000


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
    """Calculate input amount needed for desired output (legacy helper)."""
    if amount_out == 0:
        return 0

    total_fee_rate = protocol_fee_rate + platform_fee_rate + share_fee_rate
    if total_fee_rate >= 10000:
        return 0

    k = virtual_base * virtual_quote
    new_virtual_base = virtual_base - amount_out
    if new_virtual_base == 0:
        return 0

    new_virtual_quote = k // new_virtual_base
    quote_in = new_virtual_quote - virtual_quote
    return quote_in * 10000 // (10000 - total_fee_rate)


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
    """Calculate output amount for given input (legacy helper)."""
    if amount_in == 0:
        return 0

    total_fee_rate = protocol_fee_rate + platform_fee_rate + share_fee_rate
    fee = amount_in * total_fee_rate // 10000
    amount_in_after_fee = amount_in - fee

    k = virtual_base * virtual_quote
    new_virtual_quote = virtual_quote + amount_in_after_fee
    if new_virtual_quote == 0:
        return 0

    new_virtual_base = k // new_virtual_quote
    return virtual_base - new_virtual_base


def get_amount_in_net(
    amount_in: int,
    protocol_fee_rate: int,
    platform_fee_rate: int,
    share_fee_rate: int,
) -> int:
    """Calculate net input after fees."""
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
    """Compute swap amount with clamped slippage."""
    bps = clamp_slippage_basis_points(slippage_basis_points)
    if is_buy:
        amount_out = get_buy_token_amount_from_sol_amount(
            amount_in, virtual_base, virtual_quote, 0, 0, 0
        )
    else:
        amount_out = get_sell_sol_amount_from_token_amount(
            amount_in, virtual_base, virtual_quote, 0, 0, 0
        )

    min_amount_out = amount_out - (amount_out * bps // 10_000)
    return {
        "amount_out": amount_out,
        "min_amount_out": min_amount_out,
    }
