"""
Instruction builders for Sol Trade SDK
"""

from __future__ import annotations

from typing import List, Optional, Union
from abc import ABC, abstractmethod

from solders.pubkey import Pubkey
from solders.instruction import Instruction, AccountMeta

from . import (
    DexType,
    PUMPFUN_PROGRAM,
    PUMPSWAP_PROGRAM,
    TOKEN_PROGRAM,
    TOKEN_PROGRAM_2022,
    SYSTEM_PROGRAM,
    RENT,
    ASSOCIATED_TOKEN_PROGRAM,
    FEE_RECIPIENT,
    DEFAULT_SLIPPAGE,
    PumpFunParams,
    PumpSwapParams,
    BonkParams,
    RaydiumCpmmParams,
    RaydiumAmmV4Params,
    MeteoraDammV2Params,
)


def find_program_address(
    seeds: List[bytes], program_id: Pubkey
) -> tuple[Pubkey, int]:
    """
    Find program address for seeds.

    Args:
        seeds: List of seed bytes
        program_id: Program ID

    Returns:
        Tuple of (PDA, bump)
    """
    from solders.pubkey import Pubkey as SolderPubkey

    # Use solders' find_program_address
    return SolderPubkey.find_program_address(seeds, program_id)


# ============== PumpFun PDAs ==============


def get_bonding_curve_pda(mint: Pubkey) -> Pubkey:
    """Get bonding curve PDA for PumpFun"""
    pda, _ = find_program_address(
        [b"bonding-curve", bytes(mint)], PUMPFUN_PROGRAM
    )
    return pda


def get_bonding_curve_v2_pda(mint: Pubkey) -> Pubkey:
    """Get bonding curve V2 PDA for PumpFun"""
    pda, _ = find_program_address(
        [b"bonding-curve-v2", bytes(mint)], PUMPFUN_PROGRAM
    )
    return pda


def get_user_volume_accumulator_pda(user: Pubkey) -> Pubkey:
    """Get user volume accumulator PDA"""
    pda, _ = find_program_address(
        [b"user-volume-accumulator", bytes(user)], PUMPFUN_PROGRAM
    )
    return pda


def get_creator_vault_pda(creator: Pubkey) -> Pubkey:
    """Get creator vault PDA"""
    pda, _ = find_program_address(
        [b"creator-vault", bytes(creator)], PUMPFUN_PROGRAM
    )
    return pda


def get_global_account_pda() -> Pubkey:
    """Get global account PDA"""
    pda, _ = find_program_address([b"global"], PUMPFUN_PROGRAM)
    return pda


def get_event_authority_pda() -> Pubkey:
    """Get event authority PDA"""
    pda, _ = find_program_address([b"__event_authority"], PUMPFUN_PROGRAM)
    return pda


def get_associated_token_address(
    owner: Pubkey, mint: Pubkey, token_program: Pubkey = TOKEN_PROGRAM
) -> Pubkey:
    """Get associated token address"""
    pda, _ = find_program_address(
        [bytes(owner), bytes(token_program), bytes(mint)],
        ASSOCIATED_TOKEN_PROGRAM,
    )
    return pda


# ============== PumpSwap PDAs ==============


def get_pool_pda(base_mint: Pubkey, quote_mint: Pubkey) -> Pubkey:
    """Get pool PDA for PumpSwap"""
    pda, _ = find_program_address(
        [b"pool", bytes(base_mint), bytes(quote_mint)], PUMPSWAP_PROGRAM
    )
    return pda


# ============== Instruction Builders ==============


class InstructionBuilder(ABC):
    """Base class for instruction builders"""

    @abstractmethod
    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: Union[
            PumpFunParams,
            PumpSwapParams,
            BonkParams,
            RaydiumCpmmParams,
            RaydiumAmmV4Params,
            MeteoraDammV2Params,
        ],
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build buy instructions"""
        pass

    @abstractmethod
    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: Union[
            PumpFunParams,
            PumpSwapParams,
            BonkParams,
            RaydiumCpmmParams,
            RaydiumAmmV4Params,
            MeteoraDammV2Params,
        ],
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build sell instructions"""
        pass


class InstructionBuilderFactory:
    """Factory for creating instruction builders"""

    @staticmethod
    def create(dex_type: DexType) -> InstructionBuilder:
        """Create instruction builder for DEX type"""
        builders = {
            DexType.PUMPFUN: PumpFunInstructionBuilder,
            DexType.PUMPSWAP: PumpSwapInstructionBuilder,
            DexType.BONK: BonkInstructionBuilder,
            DexType.RAYDIUM_CPMM: RaydiumCpmmInstructionBuilder,
            DexType.RAYDIUM_AMM_V4: RaydiumAmmV4InstructionBuilder,
            DexType.METEORA_DAMM_V2: MeteoraDammV2InstructionBuilder,
        }

        builder_class = builders.get(dex_type)
        if builder_class is None:
            raise ValueError(f"Unsupported DEX type: {dex_type}")

        return builder_class()


class PumpFunInstructionBuilder(InstructionBuilder):
    """Instruction builder for PumpFun protocol"""

    # Instruction discriminators
    BUY_DISCRIMINATOR = bytes([102, 6, 141, 196, 242, 95, 28, 167])
    SELL_DISCRIMINATOR = bytes([187, 75, 56, 100, 133, 176, 22, 141])
    BUY_EXACT_SOL_IN_DISCRIMINATOR = bytes([133, 104, 247, 38, 153, 106, 73, 253])

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: PumpFunParams,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build buy instructions for PumpFun"""
        if input_amount == 0:
            raise ValueError("Amount cannot be zero")

        if not isinstance(protocol_params, PumpFunParams):
            raise TypeError("Invalid protocol params for PumpFun")

        instructions: List[Instruction] = []

        # Get bonding curve address
        bonding_curve_addr = protocol_params.bonding_curve.account
        if bonding_curve_addr == Pubkey.default():
            bonding_curve_addr = get_bonding_curve_pda(output_mint)

        # Get associated bonding curve
        associated_bonding_curve = protocol_params.associated_bonding_curve
        if associated_bonding_curve == Pubkey.default():
            associated_bonding_curve = get_associated_token_address(
                bonding_curve_addr, output_mint, protocol_params.token_program
            )

        # Get user token account
        user_token_account = get_associated_token_address(
            payer, output_mint, protocol_params.token_program
        )

        # Create ATA if needed
        if create_output_ata:
            create_ata_ix = self._create_ata_instruction(
                payer, output_mint, protocol_params.token_program
            )
            instructions.append(create_ata_ix)

        # Build buy instruction
        buy_ix = self._build_buy_instruction(
            payer=payer,
            mint=output_mint,
            bonding_curve=bonding_curve_addr,
            associated_bonding_curve=associated_bonding_curve,
            user_token_account=user_token_account,
            creator_vault=protocol_params.creator_vault,
            token_program=protocol_params.token_program,
            amount_in=input_amount,
            slippage=slippage_basis_points,
            is_mayhem_mode=protocol_params.bonding_curve.is_mayhem_mode,
            is_cashback_coin=protocol_params.bonding_curve.is_cashback_coin,
            use_exact_sol_in=True,
        )
        instructions.append(buy_ix)

        return instructions

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: PumpFunParams,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build sell instructions for PumpFun"""
        if input_amount == 0:
            raise ValueError("Amount cannot be zero")

        if not isinstance(protocol_params, PumpFunParams):
            raise TypeError("Invalid protocol params for PumpFun")

        instructions: List[Instruction] = []

        # Get bonding curve address
        bonding_curve_addr = protocol_params.bonding_curve.account
        if bonding_curve_addr == Pubkey.default():
            bonding_curve_addr = get_bonding_curve_pda(input_mint)

        # Get associated bonding curve
        associated_bonding_curve = protocol_params.associated_bonding_curve
        if associated_bonding_curve == Pubkey.default():
            associated_bonding_curve = get_associated_token_address(
                bonding_curve_addr, input_mint, protocol_params.token_program
            )

        # Get user token account
        user_token_account = get_associated_token_address(
            payer, input_mint, protocol_params.token_program
        )

        # Build sell instruction
        sell_ix = self._build_sell_instruction(
            payer=payer,
            mint=input_mint,
            bonding_curve=bonding_curve_addr,
            associated_bonding_curve=associated_bonding_curve,
            user_token_account=user_token_account,
            creator_vault=protocol_params.creator_vault,
            token_program=protocol_params.token_program,
            token_amount=input_amount,
            slippage=slippage_basis_points,
            is_mayhem_mode=protocol_params.bonding_curve.is_mayhem_mode,
            is_cashback_coin=protocol_params.bonding_curve.is_cashback_coin,
        )
        instructions.append(sell_ix)

        # Close token account if requested
        if close_input_ata or (
            protocol_params.close_token_account_when_sell is not None
            and protocol_params.close_token_account_when_sell
        ):
            close_ix = self._build_close_account_instruction(
                protocol_params.token_program,
                user_token_account,
                payer,
                payer,
            )
            instructions.append(close_ix)

        return instructions

    def _create_ata_instruction(
        self, payer: Pubkey, mint: Pubkey, token_program: Pubkey
    ) -> Instruction:
        """Create associated token account instruction"""
        ata = get_associated_token_address(payer, mint, token_program)

        keys = [
            AccountMeta(payer, True, True),
            AccountMeta(ata, False, True),
            AccountMeta(payer, False, False),
            AccountMeta(mint, False, False),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(token_program, False, False),
            AccountMeta(ASSOCIATED_TOKEN_PROGRAM, False, False),
            AccountMeta(RENT, False, False),
        ]

        return Instruction(ASSOCIATED_TOKEN_PROGRAM, bytes(), keys)

    def _build_buy_instruction(
        self,
        payer: Pubkey,
        mint: Pubkey,
        bonding_curve: Pubkey,
        associated_bonding_curve: Pubkey,
        user_token_account: Pubkey,
        creator_vault: Pubkey,
        token_program: Pubkey,
        amount_in: int,
        slippage: int,
        is_mayhem_mode: bool,
        is_cashback_coin: bool,
        use_exact_sol_in: bool,
    ) -> Instruction:
        """Build buy instruction"""
        global_account = get_global_account_pda()
        event_authority = get_event_authority_pda()
        bonding_curve_v2 = get_bonding_curve_v2_pda(mint)
        user_volume_accumulator = get_user_volume_accumulator_pda(payer)
        fee_recipient = self._get_fee_recipient(is_mayhem_mode)

        # Build data
        if use_exact_sol_in:
            min_tokens_out = amount_in  # Simplified
            data = bytearray(26)
            data[0:8] = self.BUY_EXACT_SOL_IN_DISCRIMINATOR
            data[8:16] = amount_in.to_bytes(8, "little")
            data[16:24] = min_tokens_out.to_bytes(8, "little")
            data[24] = 1  # Some
            data[25] = 1 if is_cashback_coin else 0
        else:
            max_sol_cost = amount_in
            data = bytearray(26)
            data[0:8] = self.BUY_DISCRIMINATOR
            data[16:24] = max_sol_cost.to_bytes(8, "little")
            data[24] = 1
            data[25] = 1 if is_cashback_coin else 0

        keys = [
            AccountMeta(global_account, False, False),
            AccountMeta(fee_recipient, False, True),
            AccountMeta(mint, False, False),
            AccountMeta(bonding_curve, False, True),
            AccountMeta(associated_bonding_curve, False, True),
            AccountMeta(user_token_account, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(token_program, False, False),
            AccountMeta(creator_vault, False, True),
            AccountMeta(event_authority, False, False),
            AccountMeta(PUMPFUN_PROGRAM, False, False),
            AccountMeta(bonding_curve_v2, False, False),
        ]

        return Instruction(PUMPFUN_PROGRAM, bytes(data), keys)

    def _build_sell_instruction(
        self,
        payer: Pubkey,
        mint: Pubkey,
        bonding_curve: Pubkey,
        associated_bonding_curve: Pubkey,
        user_token_account: Pubkey,
        creator_vault: Pubkey,
        token_program: Pubkey,
        token_amount: int,
        slippage: int,
        is_mayhem_mode: bool,
        is_cashback_coin: bool,
    ) -> Instruction:
        """Build sell instruction"""
        global_account = get_global_account_pda()
        event_authority = get_event_authority_pda()
        bonding_curve_v2 = get_bonding_curve_v2_pda(mint)
        fee_recipient = self._get_fee_recipient(is_mayhem_mode)

        min_sol_output = 0  # Simplified calculation

        data = bytearray(24)
        data[0:8] = self.SELL_DISCRIMINATOR
        data[8:16] = token_amount.to_bytes(8, "little")
        data[16:24] = min_sol_output.to_bytes(8, "little")

        keys = [
            AccountMeta(global_account, False, False),
            AccountMeta(fee_recipient, False, True),
            AccountMeta(mint, False, False),
            AccountMeta(bonding_curve, False, True),
            AccountMeta(associated_bonding_curve, False, True),
            AccountMeta(user_token_account, False, True),
            AccountMeta(payer, True, True),
            AccountMeta(SYSTEM_PROGRAM, False, False),
            AccountMeta(creator_vault, False, True),
            AccountMeta(token_program, False, False),
            AccountMeta(event_authority, False, False),
            AccountMeta(PUMPFUN_PROGRAM, False, False),
        ]

        if is_cashback_coin:
            user_volume_accumulator = get_user_volume_accumulator_pda(payer)
            keys.append(AccountMeta(user_volume_accumulator, False, True))

        keys.append(AccountMeta(bonding_curve_v2, False, False))

        return Instruction(PUMPFUN_PROGRAM, bytes(data), keys)

    def _build_close_account_instruction(
        self,
        token_program: Pubkey,
        account: Pubkey,
        owner: Pubkey,
        destination: Pubkey,
    ) -> Instruction:
        """Build close account instruction"""
        data = bytes([151, 9, 59, 186, 208, 190, 183, 75])
        keys = [
            AccountMeta(account, False, True),
            AccountMeta(destination, False, True),
            AccountMeta(owner, True, False),
        ]
        return Instruction(token_program, data, keys)

    def _get_fee_recipient(self, is_mayhem_mode: bool) -> Pubkey:
        """Get fee recipient based on mayhem mode"""
        import random

        if is_mayhem_mode:
            mayhem_recipients = [
                Pubkey.from_string("7VtWHe8WJeU9Sy5j1XF5n8qPzDtJjWxMgYVtJ89AQrVj"),
                Pubkey.from_string("82jN8eGgPvMSW1KP9W6GdW4bQ3YbB7sGgC6BhZnLVQvR"),
            ]
            return random.choice(mayhem_recipients)
        return FEE_RECIPIENT


class PumpSwapInstructionBuilder(InstructionBuilder):
    """Instruction builder for PumpSwap protocol"""

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: PumpSwapParams,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build buy instructions for PumpSwap"""
        # Simplified implementation
        return []

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: PumpSwapParams,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        """Build sell instructions for PumpSwap"""
        return []


class BonkInstructionBuilder(InstructionBuilder):
    """Instruction builder for Bonk protocol"""

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: BonkParams,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: BonkParams,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []


class RaydiumCpmmInstructionBuilder(InstructionBuilder):
    """Instruction builder for Raydium CPMM protocol"""

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: RaydiumCpmmParams,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: RaydiumCpmmParams,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []


class RaydiumAmmV4InstructionBuilder(InstructionBuilder):
    """Instruction builder for Raydium AMM V4 protocol"""

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: RaydiumAmmV4Params,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: RaydiumAmmV4Params,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []


class MeteoraDammV2InstructionBuilder(InstructionBuilder):
    """Instruction builder for Meteora DAMM V2 protocol"""

    async def build_buy_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: MeteoraDammV2Params,
        create_output_ata: bool = True,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []

    async def build_sell_instructions(
        self,
        payer: Pubkey,
        input_mint: Pubkey,
        output_mint: Pubkey,
        input_amount: int,
        slippage_basis_points: int,
        protocol_params: MeteoraDammV2Params,
        create_output_ata: bool = False,
        close_input_ata: bool = False,
    ) -> List[Instruction]:
        return []
