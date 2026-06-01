"""
Common constants and utilities for Solana trading SDK.
Contains program IDs, token addresses, and utility functions for ATA creation and WSOL handling.
"""

from typing import List, Optional, Tuple
from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta
from solders.system_program import ID as SYSTEM_PROGRAM_ID
import struct

# ============================================
# Common Program IDs
# ============================================

SYSTEM_PROGRAM: Pubkey = Pubkey.from_string("11111111111111111111111111111111")
TOKEN_PROGRAM: Pubkey = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_PROGRAM_2022: Pubkey = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")
ASSOCIATED_TOKEN_PROGRAM: Pubkey = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

# ============================================
# Common Token Mints
# ============================================

SOL_TOKEN_ACCOUNT: Pubkey = Pubkey.from_string("So11111111111111111111111111111111111111111")
WSOL_TOKEN_ACCOUNT: Pubkey = Pubkey.from_string("So11111111111111111111111111111111111111112")
USDC_TOKEN_ACCOUNT: Pubkey = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
USD1_TOKEN_ACCOUNT: Pubkey = Pubkey.from_string("USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB")

# ============================================
# Default Values
# ============================================

DEFAULT_SLIPPAGE: int = 500  # 5% in basis points


# ============================================
# Utility Functions
# ============================================

def get_associated_token_address(
    owner: Pubkey,
    mint: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Pubkey:
    """
    Derive the associated token account address for a given owner and mint.
    """
    from solders.pubkey import Pubkey as SolderPubkey

    seeds = [
        bytes(owner),
        bytes(token_program),
        bytes(mint),
    ]
    (ata, _) = SolderPubkey.find_program_address(seeds, ASSOCIATED_TOKEN_PROGRAM)
    return ata


def create_associated_token_account_idempotent_instruction(
    payer: Pubkey,
    owner: Pubkey,
    mint: Pubkey,
    token_program: Pubkey = TOKEN_PROGRAM,
) -> Instruction:
    """
    Create an idempotent instruction to create an associated token account.
    This instruction will succeed even if the account already exists.
    """
    ata = get_associated_token_address(owner, mint, token_program)

    # Discriminator for create_idempotent (Anchor IDL)
    data = b"\x01"  # create_idempotent discriminator (different from create)

    accounts = [
        AccountMeta(payer, True, True),  # payer (signer, writable)
        AccountMeta(ata, False, True),  # ata (writable)
        AccountMeta(owner, False, False),  # owner (readonly)
        AccountMeta(mint, False, False),  # mint (readonly)
        AccountMeta(SYSTEM_PROGRAM, False, False),  # system_program (readonly)
        AccountMeta(token_program, False, False),  # token_program (readonly)
    ]

    return Instruction(ASSOCIATED_TOKEN_PROGRAM, data, accounts)


def create_wsol_account_instruction(
    payer: Pubkey,
    amount: int,
) -> List[Instruction]:
    """
    Create instructions to:
    1. Create WSOL account if needed (via ATA idempotent)
    2. Transfer SOL to the WSOL account
    3. Sync the WSOL account (close will be done separately)

    Returns a list of instructions for handling WSOL.
    """
    instructions = []

    wsol_ata = get_associated_token_address(payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)

    # Create idempotent WSOL ATA
    instructions.append(
        create_associated_token_account_idempotent_instruction(
            payer, payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
        )
    )

    # Transfer SOL to WSOL ATA (system transfer)
    # The amount is transferred to the WSOL account
    from solders.system_program import transfer, TransferParams

    transfer_ix = transfer(
        TransferParams(
            from_pubkey=payer,
            to_pubkey=wsol_ata,
            lamports=amount,
        )
    )
    instructions.append(transfer_ix)

    # SPL Token SyncNative discriminator.
    sync_data = bytes([17])
    sync_accounts = [AccountMeta(wsol_ata, False, True)]
    sync_ix = Instruction(TOKEN_PROGRAM, sync_data, sync_accounts)
    instructions.append(sync_ix)

    return instructions


def close_wsol_account_instruction(
    payer: Pubkey,
) -> Instruction:
    """
    Create instruction to close WSOL account and reclaim rent.
    """
    wsol_ata = get_associated_token_address(payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM)

    close_data = bytes([9])

    accounts = [
        AccountMeta(wsol_ata, False, True),  # account to close (writable)
        AccountMeta(payer, False, True),  # destination (writable)
        AccountMeta(payer, True, False),  # owner (signer)
    ]

    return Instruction(TOKEN_PROGRAM, close_data, accounts)


def close_token_account_instruction(
    token_program: Pubkey,
    account: Pubkey,
    destination: Pubkey,
    owner: Pubkey,
) -> Instruction:
    """
    Create instruction to close a token account and reclaim rent.
    """
    close_data = bytes([9])

    accounts = [
        AccountMeta(account, False, True),  # account to close (writable)
        AccountMeta(destination, False, True),  # destination (writable)
        AccountMeta(owner, True, False),  # owner (signer)
    ]

    return Instruction(token_program, close_data, accounts)


def handle_wsol(payer: Pubkey, amount: int) -> List[Instruction]:
    """
    Handle WSOL operations: create ATA, transfer SOL, sync.
    This is the Python equivalent of the Rust handle_wsol function.
    """
    return create_wsol_account_instruction(payer, amount)


def create_wsol_ata(payer: Pubkey) -> List[Instruction]:
    """
    Create WSOL ATA without funding (for receiving WSOL).
    """
    return [
        create_associated_token_account_idempotent_instruction(
            payer, payer, WSOL_TOKEN_ACCOUNT, TOKEN_PROGRAM
        )
    ]


def close_wsol(payer: Pubkey) -> List[Instruction]:
    """
    Close WSOL ATA and reclaim rent.
    """
    return [close_wsol_account_instruction(payer)]


# ============================================
# Calculation Functions
# ============================================

def calculate_with_slippage_buy(amount: int, slippage_bps: int) -> int:
    """
    Calculate maximum input amount with slippage for buy operations.
    Returns amount * (10000 + slippage_bps) / 10000
    """
    return amount * (10000 + slippage_bps) // 10000


def calculate_with_slippage_sell(amount: int, slippage_bps: int) -> int:
    """
    Calculate minimum output amount with slippage for sell operations.
    Returns amount * (10000 - slippage_bps) / 10000
    """
    return amount * (10000 - slippage_bps) // 10000


# ============================================
# Price Calculation Functions - from Rust: src/utils/price/bonk.rs
# ============================================

DEFAULT_TOKEN_DECIMALS = 6
SOL_DECIMALS = 9


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
    return price_base_in_quote(
        virtual_base, virtual_quote, real_base, real_quote,
        DEFAULT_TOKEN_DECIMALS, SOL_DECIMALS
    )


def price_base_in_quote(
    virtual_base: int,
    virtual_quote: int,
    real_base: int,
    real_quote: int,
    base_decimals: int,
    quote_decimals: int,
) -> float:
    """
    Calculate the price of base in quote.
    100% from Rust: src/utils/price/bonk.rs price_base_in_quote

    Args:
        virtual_base: Virtual base reserves
        virtual_quote: Virtual quote reserves
        real_base: Real base reserves
        real_quote: Real quote reserves
        base_decimals: Base token decimals
        quote_decimals: Quote token decimals

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
    quote_reserves = virtual_quote + real_quote
    base_reserves = virtual_base - real_base if virtual_base > real_base else 0

    if base_reserves == 0:
        return 0.0

    if decimal_factor == 0.0:
        return 0.0

    # Use floating point calculation to avoid precision loss
    price = (quote_reserves / base_reserves) / decimal_factor

    return price
