"""
Input validators for Sol Trade SDK

Provides secure input validation for:
- RPC URLs
- Program IDs
- Amounts
- Slippage values
"""

import re
from urllib.parse import urlparse
from typing import Optional


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


# Known legitimate Solana program IDs
KNOWN_PROGRAM_IDS = {
    # PumpFun
    "pumpfun": [
        "6EF8rrecthR5Dkzon8Nwu78hRvfCKopJFfWcCzNfXt3D",  # Mainnet
    ],
    # PumpSwap
    "pumpswap": [
        "pAMMBay6oceH9fJKBRdGP4LmVn7LKwEqT7dPWn1oLKs",  # Mainnet
    ],
    # Raydium
    "raydium": [
        "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # CPMM
        "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # AMM V4
    ],
    # Meteora
    "meteora": [
        "MERLuDFBMmsHnsBPZw2sDQZHvXFM4sPkHePSuUZnPdK",  # DAMM V2
    ],
    # System programs
    "system": [
        "11111111111111111111111111111111",  # System Program
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # Token Program
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token-2022
        "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",  # Associated Token
    ],
}


def validate_rpc_url(url: str, allow_http: bool = False) -> str:
    """
    Validate RPC URL format and security.

    Args:
        url: RPC URL to validate
        allow_http: If False, only HTTPS is allowed

    Returns:
        Validated URL

    Raises:
        ValidationError: If URL is invalid or insecure
    """
    if not url:
        raise ValidationError("RPC URL cannot be empty")

    parsed = urlparse(url)

    # Check scheme
    if parsed.scheme not in ('https', 'http'):
        raise ValidationError(f"Invalid URL scheme: {parsed.scheme}. Must be http or https")

    if parsed.scheme == 'http' and not allow_http:
        raise ValidationError(
            "HTTP RPC URLs are insecure. Use HTTPS or set allow_http=True if you understand the risks"
        )

    # Check hostname
    if not parsed.hostname:
        raise ValidationError("URL must have a hostname")

    # Block localhost and private IPs in production (unless explicitly allowed)
    hostname = parsed.hostname.lower()

    # Check for common private IP ranges
    private_ip_patterns = [
        r'^127\.',
        r'^10\.',
        r'^172\.(1[6-9]|2[0-9]|3[01])\.',
        r'^192\.168\.',
        r'^0\.',
        r'^localhost$',
    ]

    for pattern in private_ip_patterns:
        if re.match(pattern, hostname):
            raise ValidationError(
                f"Private IP/localhost RPC URLs are not allowed for security: {hostname}"
            )

    # Check port
    if parsed.port and (parsed.port < 1 or parsed.port > 65535):
        raise ValidationError(f"Invalid port number: {parsed.port}")

    # Reconstruct clean URL
    clean_url = f"{parsed.scheme}://{parsed.hostname}"
    if parsed.port:
        clean_url += f":{parsed.port}"
    if parsed.path:
        clean_url += parsed.path

    return clean_url


def validate_program_id(program_id: str, expected_program: Optional[str] = None) -> str:
    """
    Validate a Solana program ID.

    Args:
        program_id: Base58-encoded program ID
        expected_program: Expected program name (e.g., 'pumpfun', 'raydium')

    Returns:
        Validated program ID

    Raises:
        ValidationError: If program ID is invalid or doesn't match expected
    """
    if not program_id:
        raise ValidationError("Program ID cannot be empty")

    # Check base58 format (rough validation)
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in program_id):
        raise ValidationError(f"Invalid base58 characters in program ID: {program_id}")

    # Check length (Solana pubkeys are 32 bytes = ~44 base58 chars)
    if len(program_id) < 32 or len(program_id) > 48:
        raise ValidationError(f"Invalid program ID length: {len(program_id)} (expected 32-48)")

    # Verify against known program IDs if expected
    if expected_program:
        expected_ids = KNOWN_PROGRAM_IDS.get(expected_program.lower(), [])
        if expected_ids and program_id not in expected_ids:
            raise ValidationError(
                f"Program ID {program_id} does not match known {expected_program} program IDs. "
                f"Expected one of: {', '.join(expected_ids[:3])}"
            )

    return program_id


def validate_amount(amount: int, name: str = "amount", allow_zero: bool = False) -> int:
    """
    Validate an amount value.

    Args:
        amount: Amount to validate
        name: Name of the amount field (for error messages)
        allow_zero: If True, zero is allowed

    Returns:
        Validated amount

    Raises:
        ValidationError: If amount is invalid
    """
    if not isinstance(amount, int):
        raise ValidationError(f"{name} must be an integer, got {type(amount).__name__}")

    if amount < 0:
        raise ValidationError(f"{name} cannot be negative: {amount}")

    if amount == 0 and not allow_zero:
        raise ValidationError(f"{name} cannot be zero")

    # Check for reasonable upper bound (prevent overflow)
    max_safe = 2**63 - 1  # Max i64
    if amount > max_safe:
        raise ValidationError(f"{name} exceeds maximum safe value: {amount} > {max_safe}")

    return amount


def validate_slippage(slippage_basis_points: int) -> int:
    """
    Validate slippage in basis points.

    Args:
        slippage_basis_points: Slippage in basis points (1 bp = 0.01%)

    Returns:
        Validated slippage

    Raises:
        ValidationError: If slippage is invalid
    """
    if not isinstance(slippage_basis_points, int):
        raise ValidationError(f"Slippage must be an integer, got {type(slippage_basis_points).__name__}")

    if slippage_basis_points < 0:
        raise ValidationError(f"Slippage cannot be negative: {slippage_basis_points}")

    if slippage_basis_points > 10_000:
        raise ValidationError(
            f"Slippage cannot exceed 10000 basis points (100%), got {slippage_basis_points}"
        )

    # Warn on high slippage
    if slippage_basis_points > 1_000:  # > 10%
        import warnings
        warnings.warn(
            f"High slippage detected: {slippage_basis_points} bp ({slippage_basis_points/100}%). "
            "This may result in significant price impact.",
            UserWarning
        )

    return slippage_basis_points


def validate_pubkey(pubkey: str, name: str = "pubkey") -> str:
    """
    Validate a Solana public key.

    Args:
        pubkey: Base58-encoded public key
        name: Name of the field (for error messages)

    Returns:
        Validated pubkey

    Raises:
        ValidationError: If pubkey is invalid
    """
    if not pubkey:
        raise ValidationError(f"{name} cannot be empty")

    # Check base58 format
    base58_chars = set('123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz')
    if not all(c in base58_chars for c in pubkey):
        raise ValidationError(f"Invalid base58 characters in {name}: {pubkey}")

    # Check length
    if len(pubkey) < 32 or len(pubkey) > 48:
        raise ValidationError(f"Invalid {name} length: {len(pubkey)} (expected 32-48)")

    return pubkey


def validate_mint_pair(input_mint: str, output_mint: str) -> None:
    """
    Validate a trading pair.

    Args:
        input_mint: Input token mint
        output_mint: Output token mint

    Raises:
        ValidationError: If pair is invalid
    """
    validate_pubkey(input_mint, "input_mint")
    validate_pubkey(output_mint, "output_mint")

    if input_mint == output_mint:
        raise ValidationError("Input and output mint cannot be the same")


def validate_transaction_size(transaction_bytes: bytes, max_size: int = 1232) -> bytes:
    """
    Validate transaction size.

    Args:
        transaction_bytes: Serialized transaction
        max_size: Maximum allowed size (default: 1232 bytes for Solana)

    Returns:
        Validated transaction bytes

    Raises:
        ValidationError: If transaction is too large
    """
    if not isinstance(transaction_bytes, bytes):
        raise ValidationError(f"Transaction must be bytes, got {type(transaction_bytes).__name__}")

    if len(transaction_bytes) > max_size:
        raise ValidationError(
            f"Transaction size {len(transaction_bytes)} exceeds maximum {max_size} bytes"
        )

    return transaction_bytes
