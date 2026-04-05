"""
Raydium CPMM instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List, Optional
from dataclasses import dataclass

# Program ID
RAYDIUM_CPMM_PROGRAM = bytes.fromhex("675c1c5e5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2")

# Discriminators
SWAP_BASE_IN_DISCRIMINATOR = bytes([248, 198, 158, 145, 225, 117, 135, 200])

# Seeds
OBSERVATION_SEED = b"observation"
POOL_SEED = b"pool"


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
    """Get pool PDA for given config and mints"""
    import hashlib
    seed = POOL_SEED + amm_config + base_mint + quote_mint
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_observation_state_pda(pool_state: bytes) -> bytes:
    """Get observation state PDA for a pool"""
    import hashlib
    seed = OBSERVATION_SEED + pool_state
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


def get_vault_account(pool_state: bytes, mint: bytes) -> bytes:
    """Get vault account for a pool and mint"""
    import hashlib
    seed = pool_state + mint + b"vault"
    hash_result = hashlib.sha256(seed).digest()
    return hash_result[:32]


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
            AccountMeta(bytes(32), False, False),  # authority (placeholder)
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
