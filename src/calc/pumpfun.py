"""
PumpFun bonding curve calculations.
Based on sol-trade-sdk Rust implementation.

Security fixes applied:
- Integer overflow protection
- Input validation
- Bounds checking
"""

try:
    from .pumpfun_exact import buy_exact, sell_exact
except ImportError:  # Existing standalone calc import support.
    from pumpfun_exact import buy_exact, sell_exact

from typing import Tuple
import sys

# Constants from Rust (src/instruction/utils/pumpfun.rs global_constants)
FEE_BASIS_POINTS = 95  # Protocol fee (NOT 100!)
CREATOR_FEE = 30  # Creator fee (NOT 50!)
INITIAL_VIRTUAL_TOKEN_RESERVES = 1_073_000_000_000_000
INITIAL_VIRTUAL_SOL_RESERVES = 30_000_000_000  # 30 SOL
INITIAL_REAL_TOKEN_RESERVES = 793_100_000_000_000
TOKEN_TOTAL_SUPPLY = 1_000_000_000_000_000
LAMPORTS_PER_SOL = 1_000_000_000

# Maximum safe values to prevent overflow
# Using a very large value suitable for Solana calculations (u128 range)
MAX_SAFE_AMOUNT = 2**127 - 1  # Support up to u128 max


class CalculationError(Exception):
    """Raised when calculation fails due to invalid input or overflow"""
    pass


def _check_overflow(a: int, b: int, operation: str = "multiply") -> None:
    """
    Check if operation would cause integer overflow.
    Note: Python ints are arbitrary precision, but we check for reasonable bounds
    to prevent memory exhaustion attacks with extremely large numbers.
    """
    # Use a very large but finite limit to prevent memory DoS
    PRACTICAL_MAX = 2**256  # Way larger than any reasonable Solana calculation

    if operation == "multiply":
        # Check if result would be unreasonably large
        if abs(a) > PRACTICAL_MAX or abs(b) > PRACTICAL_MAX:
            raise CalculationError(f"Integer overflow: operands exceed practical maximum")
        # Python can handle large ints, but warn if extremely large
        if a != 0 and abs(b) > PRACTICAL_MAX // abs(a):
            raise CalculationError(f"Integer overflow: {a} * {b} would exceed practical maximum")
    elif operation == "add":
        if abs(a) > PRACTICAL_MAX or abs(b) > PRACTICAL_MAX:
            raise CalculationError(f"Integer overflow: operands exceed practical maximum")
        if b > 0 and a > PRACTICAL_MAX - b:
            raise CalculationError(f"Integer overflow: {a} + {b}")
        if b < 0 and a < -PRACTICAL_MAX - b:
            raise CalculationError(f"Integer underflow: {a} + {b}")


def _validate_amount(amount: int, name: str = "amount") -> None:
    """Validate amount is non-negative and within safe bounds"""
    if not isinstance(amount, int):
        raise CalculationError(f"{name} must be an integer, got {type(amount)}")
    if amount < 0:
        raise CalculationError(f"{name} cannot be negative: {amount}")
    if amount > MAX_SAFE_AMOUNT:
        raise CalculationError(f"{name} exceeds maximum safe value: {amount} > {MAX_SAFE_AMOUNT}")


def _validate_slippage(slippage_basis_points: int) -> None:
    """Validate slippage is within valid range (0-10000)"""
    if not isinstance(slippage_basis_points, int):
        raise CalculationError(f"Slippage must be an integer, got {type(slippage_basis_points)}")
    if slippage_basis_points < 0 or slippage_basis_points > 10_000:
        raise CalculationError(f"Slippage must be between 0 and 10000 basis points, got {slippage_basis_points}")


def _validate_reserves(virtual_token_reserves: int, virtual_sol_reserves: int) -> None:
    """Validate reserve values"""
    _validate_amount(virtual_token_reserves, "virtual_token_reserves")
    _validate_amount(virtual_sol_reserves, "virtual_sol_reserves")
    if virtual_token_reserves == 0:
        raise CalculationError("virtual_token_reserves cannot be zero")


def _validate_creator(creator: bytes) -> None:
    """Validate creator pubkey"""
    if not isinstance(creator, bytes):
        raise CalculationError(f"Creator must be bytes, got {type(creator)}")
    if len(creator) != 32:
        raise CalculationError(f"Creator must be 32 bytes, got {len(creator)}")


def compute_fee(amount: int, fee_basis_points: int) -> int:
    """
    Compute fee for a given amount.

    Args:
        amount: Amount to compute fee for
        fee_basis_points: Fee in basis points (1 bp = 0.01%)

    Returns:
        Fee amount

    Raises:
        CalculationError: If inputs are invalid or overflow would occur
    """
    _validate_amount(amount, "amount")
    _validate_amount(fee_basis_points, "fee_basis_points")

    _check_overflow(amount, fee_basis_points, "multiply")
    return (amount * fee_basis_points) // 10_000


def get_buy_token_amount_from_sol_amount(
    virtual_token_reserves: int,
    virtual_sol_reserves: int,
    real_token_reserves: int,
    creator: bytes,
    amount: int,
) -> int:
    _validate_creator(creator)
    return buy_exact(virtual_token_reserves,virtual_sol_reserves,real_token_reserves,amount,95+(30 if creator!=bytes(32) else 0))


def get_sell_sol_amount_from_token_amount(
    virtual_token_reserves: int,
    virtual_sol_reserves: int,
    creator: bytes,
    amount: int,
) -> int:
    _validate_creator(creator)
    return sell_exact(virtual_token_reserves,virtual_sol_reserves,amount,95+(30 if creator!=bytes(32) else 0))


def calculate_with_slippage_buy(amount: int, slippage_basis_points: int) -> int:
    """
    Calculate max SOL cost with slippage for buy.

    Args:
        amount: Base amount
        slippage_basis_points: Slippage in basis points (0-10000)

    Returns:
        Amount with slippage added

    Raises:
        CalculationError: If inputs are invalid or calculation overflows

    Note:
        100% from Rust: src/utils/calc/common.rs calculate_with_slippage_buy
        Slippage is clamped to MAX_SLIPPAGE_BASIS_POINTS (9999 = 99.99%)
        to prevent the amount from doubling when slippage = 10000.
    """
    _validate_amount(amount, "amount")
    _validate_slippage(slippage_basis_points)

    # Clamp basis points to max 9999 (99.99%) to prevent amount doubling at 100%
    MAX_SLIPPAGE_BASIS_POINTS = 9999
    bps = slippage_basis_points if slippage_basis_points <= MAX_SLIPPAGE_BASIS_POINTS else MAX_SLIPPAGE_BASIS_POINTS

    # Check for overflow
    _check_overflow(amount, bps, "multiply")
    slippage_amount = (amount * bps) // 10_000

    _check_overflow(amount, slippage_amount, "add")
    return amount + slippage_amount


def calculate_with_slippage_sell(amount: int, slippage_basis_points: int) -> int:
    """
    Calculate min tokens out with slippage for sell.

    Args:
        amount: Base amount
        slippage_basis_points: Slippage in basis points (0-10000)

    Returns:
        Amount with slippage subtracted

    Raises:
        CalculationError: If inputs are invalid

    Note:
        100% from Rust: src/utils/calc/common.rs calculate_with_slippage_sell
        Returns 1 if amount <= slippage_basis_points / 10000 to ensure minimum output.
    """
    _validate_amount(amount, "amount")
    _validate_slippage(slippage_basis_points)

    # Rust: if amount <= basis_points / 10000 { 1 } else { ... }
    if amount <= slippage_basis_points // 10_000:
        return 1

    # Check for overflow in multiplication
    _check_overflow(amount, slippage_basis_points, "multiply")
    slippage_amount = (amount * slippage_basis_points) // 10_000

    return amount - slippage_amount


def lamports_to_sol(lamports: int) -> float:
    """
    Convert lamports to SOL.

    Args:
        lamports: Amount in lamports

    Returns:
        Amount in SOL

    Raises:
        CalculationError: If lamports is negative
    """
    _validate_amount(lamports, "lamports")
    return lamports / LAMPORTS_PER_SOL


def sol_to_lamports(sol: float) -> int:
    """
    Convert SOL to lamports.

    Args:
        sol: Amount in SOL

    Returns:
        Amount in lamports

    Raises:
        CalculationError: If sol is negative or would overflow
    """
    if sol < 0:
        raise CalculationError(f"SOL amount cannot be negative: {sol}")

    result = int(sol * LAMPORTS_PER_SOL)
    _validate_amount(result, "result")
    return result
