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
    """Get user volume accumulator PDA (seed must match on-chain Pump program)."""
    pda, _ = find_program_address(
        [b"user_volume_accumulator", bytes(user)], PUMPFUN_PROGRAM
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
    """PumpFun：委托 `pumpfun_builder`（含 2026-04 官方 fee recipient 账户升级）。"""

    @staticmethod
    def _protocol_params_to_pfb(protocol_params: PumpFunParams):
        """根包 `PumpFunParams` / `BondingCurveAccount` → `pumpfun_builder.PumpFunParams`。"""
        from .pumpfun_builder import PumpFunParams as PfbParams

        bc = protocol_params.bonding_curve
        assoc = protocol_params.associated_bonding_curve
        return PfbParams(
            bonding_curve_account=bc.account if bc.account != Pubkey.default() else None,
            virtual_token_reserves=bc.virtual_token_reserves,
            virtual_sol_reserves=bc.virtual_sol_reserves,
            real_token_reserves=bc.real_token_reserves,
            real_sol_reserves=bc.real_sol_reserves,
            token_total_supply=bc.token_total_supply,
            complete=bc.complete,
            creator=bc.creator,
            is_mayhem_mode=bc.is_mayhem_mode,
            is_cashback_coin=bc.is_cashback_coin,
            associated_bonding_curve=assoc if assoc != Pubkey.default() else None,
            creator_vault=protocol_params.creator_vault,
            token_program=protocol_params.token_program,
            close_token_account_when_sell=bool(protocol_params.close_token_account_when_sell),
        )

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
        """Build buy instructions for PumpFun（与 Rust / pumpfun_builder 一致）。"""
        from .pumpfun_builder import build_buy_instructions as pfb_buy

        if input_amount == 0:
            raise ValueError("Amount cannot be zero")
        if not isinstance(protocol_params, PumpFunParams):
            raise TypeError("Invalid protocol params for PumpFun")

        pfb_params = self._protocol_params_to_pfb(protocol_params)
        return pfb_buy(
            payer,
            output_mint,
            input_amount,
            pfb_params,
            slippage_basis_points,
            create_output_ata=create_output_ata,
            close_input_ata=close_input_ata,
            use_exact_sol_amount=True,
        )

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
        """Build sell instructions for PumpFun（与 Rust / pumpfun_builder 一致）。"""
        from .pumpfun_builder import build_sell_instructions as pfb_sell

        if input_amount == 0:
            raise ValueError("Amount cannot be zero")
        if not isinstance(protocol_params, PumpFunParams):
            raise TypeError("Invalid protocol params for PumpFun")

        pfb_params = self._protocol_params_to_pfb(protocol_params)
        close_token = bool(
            close_input_ata
            or (
                protocol_params.close_token_account_when_sell is not None
                and protocol_params.close_token_account_when_sell
            )
        )
        return pfb_sell(
            payer,
            input_mint,
            input_amount,
            pfb_params,
            slippage_basis_points,
            create_output_ata=create_output_ata,
            close_output_ata=False,
            close_input_ata=close_token,
        )


class PumpSwapInstructionBuilder(InstructionBuilder):
    """Instruction builder for PumpSwap protocol - Production-grade implementation"""

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
        """Build buy instructions for PumpSwap - 100% port from Rust"""
        from .pumpswap_builder import (
            build_buy_instructions,
            BuildBuyParams,
            PumpSwapParams as BuilderParams,
        )
        
        # Convert to builder params
        builder_params = BuildBuyParams(
            payer=payer,
            input_amount=input_amount,
            slippage_basis_points=slippage_basis_points,
            protocol_params=BuilderParams(
                pool=protocol_params.pool,
                base_mint=input_mint,
                quote_mint=output_mint,
                pool_base_token_account=protocol_params.pool_base_token_account,
                pool_quote_token_account=protocol_params.pool_quote_token_account,
                pool_base_token_reserves=protocol_params.pool_base_token_reserves,
                pool_quote_token_reserves=protocol_params.pool_quote_token_reserves,
                coin_creator_vault_ata=protocol_params.coin_creator_vault_ata,
                coin_creator_vault_authority=protocol_params.coin_creator_vault_authority,
                base_token_program=protocol_params.base_token_program,
                quote_token_program=protocol_params.quote_token_program,
                is_mayhem_mode=protocol_params.is_mayhem_mode,
                is_cashback_coin=protocol_params.is_cashback_coin,
            ),
            create_output_mint_ata=create_output_ata,
            close_input_mint_ata=close_input_ata,
            use_exact_quote_amount=True,
        )
        
        return build_buy_instructions(builder_params)

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
        """Build sell instructions for PumpSwap - 100% port from Rust"""
        from .pumpswap_builder import (
            build_sell_instructions,
            BuildSellParams,
            PumpSwapParams as BuilderParams,
        )
        
        # Convert to builder params
        builder_params = BuildSellParams(
            payer=payer,
            input_amount=input_amount,
            slippage_basis_points=slippage_basis_points,
            protocol_params=BuilderParams(
                pool=protocol_params.pool,
                base_mint=input_mint,
                quote_mint=output_mint,
                pool_base_token_account=protocol_params.pool_base_token_account,
                pool_quote_token_account=protocol_params.pool_quote_token_account,
                pool_base_token_reserves=protocol_params.pool_base_token_reserves,
                pool_quote_token_reserves=protocol_params.pool_quote_token_reserves,
                coin_creator_vault_ata=protocol_params.coin_creator_vault_ata,
                coin_creator_vault_authority=protocol_params.coin_creator_vault_authority,
                base_token_program=protocol_params.base_token_program,
                quote_token_program=protocol_params.quote_token_program,
                is_mayhem_mode=protocol_params.is_mayhem_mode,
                is_cashback_coin=protocol_params.is_cashback_coin,
            ),
            create_output_mint_ata=create_output_ata,
            close_input_mint_ata=close_input_ata,
        )
        
        return build_sell_instructions(builder_params)


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
