"""
Meteora Damm V2 instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List, Optional
from dataclasses import dataclass

# Program ID
METEORA DAMM_V2_PROGRAM = bytes.fromhex("a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2")

# Discriminators
SWAP_DISCRIMINATOR = bytes([248, 198, 158, 145, 225, 117, 135, 200])


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


class MeteoraDammV2InstructionBuilder:
    """Instruction builder for Meteora Damm V2 protocol"""

    @staticmethod
    def build_swap_instructions(
        payer: bytes,
        pool: bytes,
        token_a_vault: bytes,
        token_b_vault: bytes,
        token_a_mint: bytes,
        token_b_mint: bytes,
        user_source_token_account: bytes,
        user_destination_token_account: bytes,
        token_a_program: bytes,
        token_b_program: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build swap instructions for Meteora Damm V2"""

        if amount_in == 0:
            raise ValueError("Amount cannot be zero")

        # Build instruction data
        data = SWAP_DISCRIMINATOR + struct.pack("<Q", amount_in) + struct.pack("<Q", minimum_amount_out)

        # Build accounts
        accounts = [
            AccountMeta(payer, True, True),
            AccountMeta(pool, False, True),
            AccountMeta(token_a_vault, False, True),
            AccountMeta(token_b_vault, False, True),
            AccountMeta(token_a_mint, False, False),
            AccountMeta(token_b_mint, False, False),
            AccountMeta(user_source_token_account, False, True),
            AccountMeta(user_destination_token_account, False, True),
            AccountMeta(token_a_program, False, False),
            AccountMeta(token_b_program, False, False),
            AccountMeta(bytes(32), False, False),  # system program (placeholder)
        ]

        return [Instruction(METEORA DAMM_V2_PROGRAM, accounts, data)]

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        pool: bytes,
        token_a_vault: bytes,
        token_b_vault: bytes,
        output_mint: bytes,
        wsol_mint: bytes,
        user_wsol_account: bytes,
        user_token_account: bytes,
        token_a_program: bytes,
        token_b_program: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build buy instructions (swap WSOL for token)"""
        return MeteoraDammV2InstructionBuilder.build_swap_instructions(
            payer=payer,
            pool=pool,
            token_a_vault=token_a_vault,
            token_b_vault=token_b_vault,
            token_a_mint=wsol_mint,
            token_b_mint=output_mint,
            user_source_token_account=user_wsol_account,
            user_destination_token_account=user_token_account,
            token_a_program=token_a_program,
            token_b_program=token_b_program,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
        )

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        pool: bytes,
        token_a_vault: bytes,
        token_b_vault: bytes,
        input_mint: bytes,
        wsol_mint: bytes,
        user_token_account: bytes,
        user_wsol_account: bytes,
        token_a_program: bytes,
        token_b_program: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build sell instructions (swap token for WSOL)"""
        return MeteoraDammV2InstructionBuilder.build_swap_instructions(
            payer=payer,
            pool=pool,
            token_a_vault=token_a_vault,
            token_b_vault=token_b_vault,
            token_a_mint=input_mint,
            token_b_mint=wsol_mint,
            user_source_token_account=user_token_account,
            user_destination_token_account=user_wsol_account,
            token_a_program=token_a_program,
            token_b_program=token_b_program,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
        )
