"""
Raydium AMM V4 instruction utilities.
Based on sol-trade-sdk Rust implementation.
"""

import struct
from typing import List
from dataclasses import dataclass

from . import raydium_amm_v4_builder as _native
from .common import TOKEN_PROGRAM

RAYDIUM_AMM_V4_PROGRAM = bytes(_native.RAYDIUM_AMM_V4_PROGRAM_ID)
SWAP_DISCRIMINATOR = _native.SWAP_BASE_IN_DISCRIMINATOR


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


class RaydiumAmmV4InstructionBuilder:
    """Instruction builder for Raydium AMM V4 protocol"""

    @staticmethod
    def build_swap_instructions(
        payer: bytes,
        amm: bytes,
        amm_authority: bytes,
        amm_open_orders: bytes,
        amm_target_orders: bytes,
        pool_coin_token_account: bytes,
        pool_pc_token_account_account: bytes,
        serum_program: bytes,
        serum_market: bytes,
        serum_bids: bytes,
        serum_asks: bytes,
        serum_event_queue: bytes,
        serum_coin_vault_account: bytes,
        serum_pc_vault_account: bytes,
        serum_vault_signer: bytes,
        user_source_token_account: bytes,
        user_destination_token_account: bytes,
        user_source_owner: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build swap instructions for Raydium AMM V4"""

        if amount_in == 0:
            raise ValueError("Amount cannot be zero")

        # Build instruction data
        # Raydium AMM V4 uses a simple swap instruction
        data = SWAP_DISCRIMINATOR + struct.pack("<Q", amount_in) + struct.pack("<Q", minimum_amount_out)

        # Legacy SwapBaseIn has 18 accounts including the token program.
        accounts = [
            AccountMeta(bytes(TOKEN_PROGRAM), False, False),
            AccountMeta(amm, False, True),
            AccountMeta(amm_authority, False, False),
            AccountMeta(amm_open_orders, False, True),
            AccountMeta(amm_target_orders, False, True),
            AccountMeta(pool_coin_token_account, False, True),
            AccountMeta(pool_pc_token_account_account, False, True),
            AccountMeta(serum_program, False, False),
            AccountMeta(serum_market, False, True),
            AccountMeta(serum_bids, False, True),
            AccountMeta(serum_asks, False, True),
            AccountMeta(serum_event_queue, False, True),
            AccountMeta(serum_coin_vault_account, False, True),
            AccountMeta(serum_pc_vault_account, False, True),
            AccountMeta(serum_vault_signer, False, False),
            AccountMeta(user_source_token_account, False, True),
            AccountMeta(user_destination_token_account, False, True),
            AccountMeta(user_source_owner, True, False),
        ]

        return [Instruction(RAYDIUM_AMM_V4_PROGRAM, accounts, data)]

    @staticmethod
    def build_buy_instructions(
        payer: bytes,
        amm: bytes,
        amm_authority: bytes,
        amm_open_orders: bytes,
        amm_target_orders: bytes,
        pool_coin_token_account: bytes,
        pool_pc_token_account_account: bytes,
        serum_program: bytes,
        serum_market: bytes,
        serum_bids: bytes,
        serum_asks: bytes,
        serum_event_queue: bytes,
        serum_coin_vault_account: bytes,
        serum_pc_vault_account: bytes,
        serum_vault_signer: bytes,
        user_wsol_account: bytes,
        user_token_account: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build buy instructions (swap WSOL for token)"""
        return RaydiumAmmV4InstructionBuilder.build_swap_instructions(
            payer=payer,
            amm=amm,
            amm_authority=amm_authority,
            amm_open_orders=amm_open_orders,
            amm_target_orders=amm_target_orders,
            pool_coin_token_account=pool_coin_token_account,
            pool_pc_token_account_account=pool_pc_token_account_account,
            serum_program=serum_program,
            serum_market=serum_market,
            serum_bids=serum_bids,
            serum_asks=serum_asks,
            serum_event_queue=serum_event_queue,
            serum_coin_vault_account=serum_coin_vault_account,
            serum_pc_vault_account=serum_pc_vault_account,
            serum_vault_signer=serum_vault_signer,
            user_source_token_account=user_wsol_account,
            user_destination_token_account=user_token_account,
            user_source_owner=payer,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
        )

    @staticmethod
    def build_sell_instructions(
        payer: bytes,
        amm: bytes,
        amm_authority: bytes,
        amm_open_orders: bytes,
        amm_target_orders: bytes,
        pool_coin_token_account: bytes,
        pool_pc_token_account_account: bytes,
        serum_program: bytes,
        serum_market: bytes,
        serum_bids: bytes,
        serum_asks: bytes,
        serum_event_queue: bytes,
        serum_coin_vault_account: bytes,
        serum_pc_vault_account: bytes,
        serum_vault_signer: bytes,
        user_token_account: bytes,
        user_wsol_account: bytes,
        amount_in: int,
        minimum_amount_out: int,
    ) -> List[Instruction]:
        """Build sell instructions (swap token for WSOL)"""
        return RaydiumAmmV4InstructionBuilder.build_swap_instructions(
            payer=payer,
            amm=amm,
            amm_authority=amm_authority,
            amm_open_orders=amm_open_orders,
            amm_target_orders=amm_target_orders,
            pool_coin_token_account=pool_coin_token_account,
            pool_pc_token_account_account=pool_pc_token_account_account,
            serum_program=serum_program,
            serum_market=serum_market,
            serum_bids=serum_bids,
            serum_asks=serum_asks,
            serum_event_queue=serum_event_queue,
            serum_coin_vault_account=serum_coin_vault_account,
            serum_pc_vault_account=serum_pc_vault_account,
            serum_vault_signer=serum_vault_signer,
            user_source_token_account=user_token_account,
            user_destination_token_account=user_wsol_account,
            user_source_owner=payer,
            amount_in=amount_in,
            minimum_amount_out=minimum_amount_out,
        )
