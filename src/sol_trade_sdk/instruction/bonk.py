"""
Bonk instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List, Optional, Tuple
from dataclasses import dataclass

# Program ID
BONK_PROGRAM = bytes.fromhex("5c11d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2")

# Discriminators
BUY_DISCRIMINATOR = bytes([102, 6, 61, 18, 1, 218, 235, 234])
SELL_DISCRIMINATOR = bytes([51, 230, 133, 164, 1, 127, 131, 173])

# Fee rates (basis points)
PROTOCOL_FEE_RATE = 100  # 1%
PLATFORM_FEE_RATE = 50   # 0.5%
SHARE_FEE_RATE = 25      # 0.25%

# Default virtual reserves
DEFAULT_VIRTUAL_BASE = 1073025605596382
DEFAULT_VIRTUAL_QUOTE = 30000852951


@dataclass
class AccountMeta:
    """Account metadata for instructions"""
    pubkey: bytes
    is_signer: bool
    is_writable: bool


@dataclass
class Instruction:
    """Solana instruction"""
    program_id: bytes
    accounts: List[AccountMeta]
    data: bytes


def get_pool_pda(base_mint: bytes, quote_mint: bytes) -> bytes:
    """Get pool PDA for given base and quote mints"""
    import hashlib
    seed = b"pool" + base_mint + quote_mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_platform_associated_account(platform_config: bytes) -> bytes:
    """Get platform associated account"""
    import hashlib
    seed = b"platform" + platform_config
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_creator_associated_account(creator: bytes) -> bytes:
    """Get creator associated account"""
    import hashlib
    seed = b"creator" + creator
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


class BonkInstructionBuilder:
    """Instruction builder for Bonk protocol"""

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        pool_state: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        base_vault: bytes,
        quote_vault: bytes,
        platform_config: bytes,
        platform_associated_account: bytes,
        creator_associated_account: bytes,
        global_config: bytes,
        user_base_token_account: bytes,
        user_quote_token_account: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build buy instructions for Bonk"""

        if amount_in == 0:
            raise ValueError("Amount cannot be zero")

        # Build instruction data
        data = BUY_DISCRIMINATOR + struct.pack("<Q", amount_in) + struct.pack("<Q", minimum_amount_out)

        # Build accounts
        accounts = [
            AccountMeta(pool_state, False, True),
            AccountMeta(base_mint, False, False),
            AccountMeta(quote_mint, False, False),
            AccountMeta(base_vault, False, True),
            AccountMeta(quote_vault, False, True),
            AccountMeta(platform_config, False, False),
            AccountMeta(platform_associated_account, False, True),
            AccountMeta(creator_associated_account, False, True),
            AccountMeta(global_config, False, False),
            AccountMeta(user_base_token_account, False, True),
            AccountMeta(user_quote_token_account, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(bytes(32), False, False),  # token program (placeholder)
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
        ]

        return [Instruction(BONK_PROGRAM, accounts, data)]

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        pool_state: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        base_vault: bytes,
        quote_vault: bytes,
        platform_config: bytes,
        platform_associated_account: bytes,
        creator_associated_account: bytes,
        global_config: bytes,
        user_base_token_account: bytes,
        user_quote_token_account: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build sell instructions for Bonk"""

        if amount_in == 0:
            raise ValueError("Amount cannot be zero")

        # Build instruction data
        data = SELL_DISCRIMINATOR + struct.pack("<Q", amount_in) + struct.pack("<Q", minimum_amount_out)

        # Build accounts
        accounts = [
            AccountMeta(pool_state, False, True),
            AccountMeta(base_mint, False, False),
            AccountMeta(quote_mint, False, False),
            AccountMeta(base_vault, False, True),
            AccountMeta(quote_vault, False, True),
            AccountMeta(platform_config, False, False),
            AccountMeta(platform_associated_account, False, True),
            AccountMeta(creator_associated_account, False, True),
            AccountMeta(global_config, False, False),
            AccountMeta(user_base_token_account, False, True),
            AccountMeta(user_quote_token_account, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(bytes(32), False, False),  # token program (placeholder)
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
        ]

        return [Instruction(BONK_PROGRAM, accounts, data)]
