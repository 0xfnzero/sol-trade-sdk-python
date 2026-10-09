"""
Bonk instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List
from dataclasses import dataclass

from solders.pubkey import Pubkey
from . import bonk_builder as _native
from .common import TOKEN_PROGRAM, SYSTEM_PROGRAM

BONK_PROGRAM = bytes(_native.BONK_PROGRAM_ID)
BUY_DISCRIMINATOR = _native.BUY_EXACT_IN_DISCRIMINATOR
SELL_DISCRIMINATOR = _native.SELL_EXACT_IN_DISCRIMINATOR
PROTOCOL_FEE_RATE = _native.PROTOCOL_FEE_RATE
PLATFORM_FEE_RATE = _native.PLATFORM_FEE_RATE
SHARE_FEE_RATE = _native.SHARE_FEE_RATE

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
    return bytes(_native.get_pool_pda(Pubkey.from_bytes(base_mint), Pubkey.from_bytes(quote_mint)))


def get_platform_associated_account(platform_config: bytes) -> bytes:
    """Derive the platform's default WSOL quote account."""
    return bytes(_native.get_platform_associated_account(Pubkey.from_bytes(platform_config)))


def get_creator_associated_account(creator: bytes) -> bytes:
    """Derive the creator's default WSOL quote account."""
    return bytes(_native.get_creator_associated_account(Pubkey.from_bytes(creator)))


def _build(discriminator, payer, pool_state, base_mint, quote_mint, base_vault,
           quote_vault, platform_config, platform_associated_account,
           creator_associated_account, global_config, user_base_token_account,
           user_quote_token_account, amount_in, minimum_amount_out):
    if amount_in == 0:
        raise ValueError("Amount cannot be zero")
    data = discriminator + struct.pack("<QQQ", amount_in, minimum_amount_out, SHARE_FEE_RATE)
    keys = [payer, bytes(_native.AUTHORITY), global_config, platform_config,
            pool_state, user_base_token_account, user_quote_token_account,
            base_vault, quote_vault, base_mint, quote_mint, bytes(TOKEN_PROGRAM),
            bytes(TOKEN_PROGRAM), bytes(_native.EVENT_AUTHORITY), BONK_PROGRAM,
            bytes(SYSTEM_PROGRAM), platform_associated_account, creator_associated_account]
    accounts = [AccountMeta(key, index == 0, index == 0 or 4 <= index <= 8 or index >= 16)
                for index, key in enumerate(keys)]
    return [Instruction(BONK_PROGRAM, accounts, data)]


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
        """Build the official LaunchLab buy_exact_in instruction (SPL Token)."""
        return _build(BUY_DISCRIMINATOR, payer, pool_state, base_mint, quote_mint,
                      base_vault, quote_vault, platform_config, platform_associated_account,
                      creator_associated_account, global_config, user_base_token_account,
                      user_quote_token_account, amount_in, minimum_amount_out)

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
        """Build the official LaunchLab sell_exact_in instruction (SPL Token)."""
        return _build(SELL_DISCRIMINATOR, payer, pool_state, base_mint, quote_mint,
                      base_vault, quote_vault, platform_config, platform_associated_account,
                      creator_associated_account, global_config, user_base_token_account,
                      user_quote_token_account, amount_in, minimum_amount_out)
