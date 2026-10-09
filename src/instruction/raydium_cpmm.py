"""
Raydium CPMM instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List, Optional
from dataclasses import dataclass

from solders.pubkey import Pubkey
from . import raydium_cpmm_builder as _native

# Share the official ABI and PDA implementation with the native builder.
RAYDIUM_CPMM_PROGRAM = bytes(_native.RAYDIUM_CPMM_PROGRAM_ID)
SWAP_BASE_IN_DISCRIMINATOR = _native.SWAP_BASE_IN_DISCRIMINATOR
OBSERVATION_SEED = _native.OBSERVATION_STATE_SEED
POOL_SEED = _native.POOL_SEED


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


def get_pool_pda(amm_config: bytes, base_mint: bytes, quote_mint: bytes) -> bytes:
    """Derive the official pool PDA for mints in caller-supplied order."""
    return bytes(_native.get_pool_pda(*map(Pubkey.from_bytes, (amm_config, base_mint, quote_mint))))


def get_observation_state_pda(pool_state: bytes) -> bytes:
    return bytes(_native.get_observation_state_pda(Pubkey.from_bytes(pool_state)))


def get_vault_account(pool_state: bytes, mint: bytes) -> bytes:
    return bytes(_native.get_vault_pda(Pubkey.from_bytes(pool_state), Pubkey.from_bytes(mint)))


class RaydiumCpmmInstructionBuilder:
    """Instruction builder for Raydium CPMM protocol"""

    @staticmethod
    def build_swap_instructions(
        payer: bytes,
        amm_config: bytes,
        pool_state: bytes,
        input_token_account: bytes,
        output_token_account: bytes,
        input_vault: bytes,
        output_vault: bytes,
        input_token_program: bytes,
        output_token_program: bytes,
        input_mint: bytes,
        output_mint: bytes,
        amount_in: int,
        minimum_amount_out: int,
        observation_state: Optional[bytes] = None,
    ) -> List[Instruction]:
        """Build swap instructions for Raydium CPMM"""

        if amount_in == 0:
            raise ValueError("Amount cannot be zero")

        # Get observation state if not provided
        if observation_state is None:
            observation_state = get_observation_state_pda(pool_state)

        # Build instruction data
        data = SWAP_BASE_IN_DISCRIMINATOR + struct.pack("<Q", amount_in) + struct.pack("<Q", minimum_amount_out)

        # Build accounts (13 accounts)
        accounts = [
            AccountMeta(payer, True, True),
            AccountMeta(bytes(_native.AUTHORITY), False, False),
            AccountMeta(amm_config, False, False),
            AccountMeta(pool_state, False, True),
            AccountMeta(input_token_account, False, True),
            AccountMeta(output_token_account, False, True),
            AccountMeta(input_vault, False, True),
            AccountMeta(output_vault, False, True),
            AccountMeta(input_token_program, False, False),
            AccountMeta(output_token_program, False, False),
            AccountMeta(input_mint, False, False),
            AccountMeta(output_mint, False, False),
            AccountMeta(observation_state, False, True),
        ]

        return [Instruction(RAYDIUM_CPMM_PROGRAM, accounts, data)]

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        amm_config: bytes,
        pool_state: bytes,
        output_mint: bytes,
        wsol_mint: bytes,
        input_token_account: bytes,
        output_token_account: bytes,
        input_vault: bytes,
        output_vault: bytes,
        token_program: bytes,
        amount_in: int,
        minimum_amount_out: int,
        observation_state: Optional[bytes] = None,
    ) -> List[Instruction]:
        """Build buy instructions (swap WSOL for token)"""
        return RaydiumCpmmInstructionBuilder.build_swap_instructions(
            payer=payer,
            amm_config=amm_config,
            pool_state=pool_state,
            input_token_account=input_token_account,
            output_token_account=output_token_account,
            input_vault=input_vault,
            output_vault=output_vault,
            input_token_program=token_program,
            output_token_program=token_program,
            input_mint=wsol_mint,
            output_mint=output_mint,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
            observation_state=observation_state,
        )

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        amm_config: bytes,
        pool_state: bytes,
        input_mint: bytes,
        wsol_mint: bytes,
        input_token_account: bytes,
        output_token_account: bytes,
        input_vault: bytes,
        output_vault: bytes,
        token_program: bytes,
        amount_in: int,
        minimum_amount_out: int,
        observation_state: Optional[bytes] = None,
    ) -> List[Instruction]:
        """Build sell instructions (swap token for WSOL)"""
        return RaydiumCpmmInstructionBuilder.build_swap_instructions(
            payer=payer,
            amm_config=amm_config,
            pool_state=pool_state,
            input_token_account=input_token_account,
            output_token_account=output_token_account,
            input_vault=input_vault,
            output_vault=output_vault,
            input_token_program=token_program,
            output_token_program=token_program,
            input_mint=input_mint,
            output_mint=wsol_mint,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
            observation_state=observation_state,
        )
