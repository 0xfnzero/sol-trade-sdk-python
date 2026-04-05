"""
High-Performance Complete Instruction Builder for Sol Trade SDK
Implements all DEX protocols with optimized instruction building.
"""

from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass, field
import struct

from .spl_token.token import (
    Instruction,
    AccountMeta,
    WSOL_MINT,
    TOKEN_PROGRAM_ID,
    base58_decode,
    base58_encode,
)
from .seed.pda import (
    find_program_address,
    get_bonding_curve_pda,
    get_global_account_pda,
    get_fee_recipient_pda,
    get_event_authority_pda,
    get_user_volume_accumulator_pda,
    get_pumpswap_pool_pda,
    get_associated_token_address,
    PUMPFUN_PROGRAM_ID,
    PUMPSWAP_PROGRAM_ID,
    RAYDIUM_AMM_V4_PROGRAM_ID,
    RAYDIUM_CPMM_PROGRAM_ID,
    METEORA_DAMM_V2_PROGRAM_ID,
)


# ===== Constants =====

# PumpFun discriminators
PUMPFUN_CREATE = bytes([0x18, 0x13, 0x4f, 0xbb, 0xe3, 0xb7, 0x96, 0xd8])
PUMPFUN_BUY = bytes([0x66, 0x06, 0x3d, 0x12, 0x01, 0xda, 0xeb, 0xea])
PUMPFUN_SELL = bytes([0x33, 0xe8, 0x85, 0x76, 0x0d, 0xdd, 0xc3, 0xf9])
PUMPFUN_BUY_EXACT_SOL = bytes([0xf8, 0xc6, 0x9e, 0x4f, 0x85, 0x2d, 0xa5, 0x3e])
PUMPFUN_SELL_EXACT_SOL = bytes([0xb6, 0x2d, 0x0c, 0x2a, 0x8a, 0x43, 0x3d, 0x14])

# PumpSwap discriminators
PUMPSWAP_BUY = bytes([0x66, 0x06, 0x3d, 0x12, 0x01, 0xda, 0xeb, 0xea])
PUMPSWAP_SELL = bytes([0x33, 0xe8, 0x85, 0x76, 0x0d, 0xdd, 0xc3, 0xf9])

# Raydium discriminators
RAYDIUM_SWAP = bytes([0xf8, 0xc6, 0x9e, 0x4f, 0x85, 0x2d, 0xa5, 0x3e])


# ===== Build Parameters =====

@dataclass
class BuildParams:
    """Parameters for building instructions"""
    payer: bytes
    input_mint: bytes
    output_mint: bytes
    input_amount: int
    slippage_bps: int = 500
    protocol_params: Optional[Any] = None
    create_output_ata: bool = True
    close_input_ata: bool = False
    use_seed_optimize: bool = False
    fixed_output_amount: Optional[int] = None
    use_exact_sol_amount: bool = True


@dataclass
class PumpFunParams:
    """PumpFun protocol parameters"""
    bonding_curve: bytes = field(default_factory=lambda: bytes(32))
    associated_bonding_curve: bytes = field(default_factory=lambda: bytes(32))
    creator_vault: bytes = field(default_factory=lambda: bytes(32))
    token_program: bytes = field(default_factory=lambda: base58_decode(TOKEN_PROGRAM_ID))
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    close_token_account_on_sell: bool = False


@dataclass
class PumpSwapParams:
    """PumpSwap protocol parameters"""
    pool: bytes = field(default_factory=lambda: bytes(32))
    pool_base_token_account: bytes = field(default_factory=lambda: bytes(32))
    pool_quote_token_account: bytes = field(default_factory=lambda: bytes(32))
    base_token_program: bytes = field(default_factory=lambda: base58_decode(TOKEN_PROGRAM_ID))
    quote_token_program: bytes = field(default_factory=lambda: base58_decode(TOKEN_PROGRAM_ID))


# ===== PumpFun Instruction Builder =====

class PumpFunInstructionBuilder:
    """Builds instructions for PumpFun protocol"""

    @staticmethod
    def build_buy_instructions(params: BuildParams) -> List[Instruction]:
        """Build buy instructions for PumpFun"""
        protocol_params: PumpFunParams = params.protocol_params
        instructions = []

        # Get bonding curve PDA
        bonding_curve_pda = get_bonding_curve_pda(
            base58_encode(params.output_mint)
        )
        bonding_curve = bonding_curve_pda.pubkey

        # Get associated bonding curve token account
        associated_bonding_curve = get_associated_token_address(
            base58_encode(bonding_curve),
            base58_encode(params.output_mint),
        )

        # Get user token account (ATA)
        user_token_account = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.output_mint),
        )

        # Get fee recipient
        fee_recipient_pda = get_fee_recipient_pda(protocol_params.is_mayhem_mode)
        fee_recipient = fee_recipient_pda.pubkey

        # Build instruction data
        if params.use_exact_sol_amount:
            # Buy exact SOL in
            amount_out_min = params.input_amount * (10000 - params.slippage_bps) // 10000
            track_volume = b"\x01\x01" if protocol_params.is_cashback_coin else b"\x01\x00"
            data = PUMPFUN_BUY_EXACT_SOL + struct.pack("<Q", params.input_amount) + struct.pack("<Q", amount_out_min) + track_volume
        else:
            # Regular buy
            max_sol_cost = params.input_amount * (10000 + params.slippage_bps) // 10000
            data = PUMPFUN_BUY + struct.pack("<Q", params.fixed_output_amount or 0) + struct.pack("<Q", max_sol_cost)

        # Build accounts
        accounts = [
            # Global
            AccountMeta(get_global_account_pda().pubkey, False, False),
            # Fee recipient
            AccountMeta(fee_recipient, False, True),
            # Mint
            AccountMeta(params.output_mint, False, False),
            # Bonding curve
            AccountMeta(bonding_curve, False, True),
            # Associated bonding curve
            AccountMeta(associated_bonding_curve, False, True),
            # User token account
            AccountMeta(user_token_account, False, True),
            # User
            AccountMeta(params.payer, True, True),
            # System program
            AccountMeta(base58_decode("11111111111111111111111111111111"), False, False),
            # Token program
            AccountMeta(protocol_params.token_program, False, False),
            # Creator vault
            AccountMeta(protocol_params.creator_vault, False, True),
            # Event authority
            AccountMeta(get_event_authority_pda().pubkey, False, False),
            # Program
            AccountMeta(base58_decode(PUMPFUN_PROGRAM_ID), False, False),
        ]

        # Add cashback account if needed
        if protocol_params.is_cashback_coin:
            user_volume = get_user_volume_accumulator_pda(
                base58_encode(params.payer)
            )
            accounts.append(AccountMeta(user_volume.pubkey, False, True))

        instructions.append(Instruction(
            program_id=base58_decode(PUMPFUN_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        return instructions

    @staticmethod
    def build_sell_instructions(params: BuildParams) -> List[Instruction]:
        """Build sell instructions for PumpFun"""
        protocol_params: PumpFunParams = params.protocol_params
        instructions = []

        # Get bonding curve PDA
        bonding_curve_pda = get_bonding_curve_pda(
            base58_encode(params.input_mint)
        )
        bonding_curve = bonding_curve_pda.pubkey

        # Get associated bonding curve token account
        associated_bonding_curve = get_associated_token_address(
            base58_encode(bonding_curve),
            base58_encode(params.input_mint),
        )

        # Get user token account (ATA)
        user_token_account = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.input_mint),
        )

        # Get fee recipient
        fee_recipient_pda = get_fee_recipient_pda(protocol_params.is_mayhem_mode)
        fee_recipient = fee_recipient_pda.pubkey

        # Build instruction data
        min_sol_output = params.input_amount * (10000 - params.slippage_bps) // 10000
        data = PUMPFUN_SELL + struct.pack("<Q", params.input_amount) + struct.pack("<Q", min_sol_output)

        # Build accounts
        accounts = [
            # Global
            AccountMeta(get_global_account_pda().pubkey, False, False),
            # Fee recipient
            AccountMeta(fee_recipient, False, True),
            # Mint
            AccountMeta(params.input_mint, False, False),
            # Bonding curve
            AccountMeta(bonding_curve, False, True),
            # Associated bonding curve
            AccountMeta(associated_bonding_curve, False, True),
            # User token account
            AccountMeta(user_token_account, False, True),
            # User
            AccountMeta(params.payer, True, True),
            # System program
            AccountMeta(base58_decode("11111111111111111111111111111111"), False, False),
            # Creator vault
            AccountMeta(protocol_params.creator_vault, False, True),
            # Token program
            AccountMeta(protocol_params.token_program, False, False),
            # Event authority
            AccountMeta(get_event_authority_pda().pubkey, False, False),
            # Program
            AccountMeta(base58_decode(PUMPFUN_PROGRAM_ID), False, False),
        ]

        # Add cashback account if needed
        if protocol_params.is_cashback_coin:
            user_volume = get_user_volume_accumulator_pda(
                base58_encode(params.payer)
            )
            accounts.append(AccountMeta(user_volume.pubkey, False, True))

        instructions.append(Instruction(
            program_id=base58_decode(PUMPFUN_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        # Close token account if requested
        if params.close_input_ata or protocol_params.close_token_account_on_sell:
            from .spl_token.token import close_account_instruction
            close_ix = close_account_instruction(
                user_token_account,
                params.payer,
                params.payer,
            )
            instructions.append(close_ix)

        return instructions


# ===== PumpSwap Instruction Builder =====

class PumpSwapInstructionBuilder:
    """Builds instructions for PumpSwap protocol"""

    @staticmethod
    def build_buy_instructions(params: BuildParams) -> List[Instruction]:
        """Build buy instructions for PumpSwap"""
        protocol_params: PumpSwapParams = params.protocol_params
        instructions = []

        # Get user accounts
        user_quote_account = get_associated_token_address(
            base58_encode(params.payer),
            WSOL_MINT,  # Quote is usually WSOL
        )
        user_base_account = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.output_mint),
        )

        # Build instruction data
        amount_out_min = params.input_amount * (10000 - params.slippage_bps) // 10000
        data = PUMPSWAP_BUY + struct.pack("<Q", params.input_amount) + struct.pack("<Q", amount_out_min)

        # Build accounts
        accounts = [
            # Pool
            AccountMeta(protocol_params.pool, False, True),
            # Pool base token account
            AccountMeta(protocol_params.pool_base_token_account, False, True),
            # Pool quote token account
            AccountMeta(protocol_params.pool_quote_token_account, False, True),
            # User base account
            AccountMeta(user_base_account, False, True),
            # User quote account
            AccountMeta(user_quote_account, False, True),
            # User
            AccountMeta(params.payer, True, True),
            # Base token program
            AccountMeta(protocol_params.base_token_program, False, False),
            # Quote token program
            AccountMeta(protocol_params.quote_token_program, False, False),
        ]

        instructions.append(Instruction(
            program_id=base58_decode(PUMPSWAP_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        return instructions

    @staticmethod
    def build_sell_instructions(params: BuildParams) -> List[Instruction]:
        """Build sell instructions for PumpSwap"""
        protocol_params: PumpSwapParams = params.protocol_params
        instructions = []

        # Get user accounts
        user_base_account = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.input_mint),
        )
        user_quote_account = get_associated_token_address(
            base58_encode(params.payer),
            WSOL_MINT,  # Quote is usually WSOL
        )

        # Build instruction data
        amount_out_min = params.input_amount * (10000 - params.slippage_bps) // 10000
        data = PUMPSWAP_SELL + struct.pack("<Q", params.input_amount) + struct.pack("<Q", amount_out_min)

        # Build accounts
        accounts = [
            # Pool
            AccountMeta(protocol_params.pool, False, True),
            # Pool base token account
            AccountMeta(protocol_params.pool_base_token_account, False, True),
            # Pool quote token account
            AccountMeta(protocol_params.pool_quote_token_account, False, True),
            # User base account
            AccountMeta(user_base_account, False, True),
            # User quote account
            AccountMeta(user_quote_account, False, True),
            # User
            AccountMeta(params.payer, True, True),
            # Base token program
            AccountMeta(protocol_params.base_token_program, False, False),
            # Quote token program
            AccountMeta(protocol_params.quote_token_program, False, False),
        ]

        instructions.append(Instruction(
            program_id=base58_decode(PUMPSWAP_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        return instructions


# ===== Raydium Instruction Builder =====

class RaydiumCpmmInstructionBuilder:
    """Builds instructions for Raydium CPMM"""

    @staticmethod
    def build_swap_instructions(
        params: BuildParams,
        pool: bytes,
        pool_authority: bytes,
        pool_token_a: bytes,
        pool_token_b: bytes,
        is_buy: bool,
    ) -> List[Instruction]:
        """Build swap instructions"""
        instructions = []

        # Get user token accounts
        user_source = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.input_mint),
        )
        user_dest = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.output_mint),
        )

        # Build instruction data
        amount_out_min = params.input_amount * (10000 - params.slippage_bps) // 10000
        data = RAYDIUM_SWAP + struct.pack("<Q", params.input_amount) + struct.pack("<Q", amount_out_min)

        accounts = [
            AccountMeta(pool, False, True),
            AccountMeta(pool_authority, False, False),
            AccountMeta(pool_token_a, False, True),
            AccountMeta(pool_token_b, False, True),
            AccountMeta(user_source, False, True),
            AccountMeta(user_dest, False, True),
            AccountMeta(params.payer, True, True),
        ]

        instructions.append(Instruction(
            program_id=base58_decode(RAYDIUM_CPMM_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        return instructions


# ===== Meteora Instruction Builder =====

class MeteoraInstructionBuilder:
    """Builds instructions for Meteora DAMM V2"""

    @staticmethod
    def build_swap_instructions(
        params: BuildParams,
        pool: bytes,
        pool_authority: bytes,
        pool_token_a: bytes,
        pool_token_b: bytes,
    ) -> List[Instruction]:
        """Build swap instructions"""
        instructions = []

        # Get user token accounts
        user_source = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.input_mint),
        )
        user_dest = get_associated_token_address(
            base58_encode(params.payer),
            base58_encode(params.output_mint),
        )

        # Build instruction data
        amount_out_min = params.input_amount * (10000 - params.slippage_bps) // 10000
        data = struct.pack("<Q", params.input_amount) + struct.pack("<Q", amount_out_min)

        accounts = [
            AccountMeta(pool, False, True),
            AccountMeta(pool_authority, False, False),
            AccountMeta(pool_token_a, False, True),
            AccountMeta(pool_token_b, False, True),
            AccountMeta(user_source, False, True),
            AccountMeta(user_dest, False, True),
            AccountMeta(params.payer, True, True),
        ]

        instructions.append(Instruction(
            program_id=base58_decode(METEORA_DAMM_V2_PROGRAM_ID),
            accounts=accounts,
            data=data,
        ))

        return instructions
