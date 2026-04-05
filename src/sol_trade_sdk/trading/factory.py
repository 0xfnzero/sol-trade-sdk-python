"""
Trading factory and executor.
Based on sol-trade-sdk Rust implementation.
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from .params import (
    DexType,
    TradeType,
    PumpFunParams,
    PumpSwapParams,
    BonkParams,
    RaydiumCpmmParams,
    RaydiumAmmV4Params,
    MeteoraDammV2Params,
)


class TradeExecutor(ABC):
    """Abstract base class for trade executors"""

    @abstractmethod
    async def execute_buy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy trade"""
        pass

    @abstractmethod
    async def execute_sell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell trade"""
        pass


class PumpFunExecutor(TradeExecutor):
    """PumpFun trade executor"""

    async def execute_buy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on PumpFun"""
        from ..instruction.pumpfun import PumpFunInstructionBuilder

        instructions = PumpFunInstructionBuilder.build_buy_instructions(
            payer=params["payer"],
            output_mint=params["output_mint"],
            input_amount=params["input_amount"],
            slippage_basis_points=params.get("slippage_basis_points", 100),
            bonding_curve=params["bonding_curve"],
            creator_vault=params["creator_vault"],
            associated_bonding_curve=params["associated_bonding_curve"],
            token_program=params.get("token_program", bytes(32)),
            create_output_mint_ata=params.get("create_output_mint_ata", True),
            use_exact_sol_amount=params.get("use_exact_sol_amount", True),
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "PumpFun",
            "type": "buy",
        }

    async def execute_sell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on PumpFun"""
        from ..instruction.pumpfun import PumpFunInstructionBuilder

        instructions = PumpFunInstructionBuilder.build_sell_instructions(
            payer=params["payer"],
            input_mint=params["input_mint"],
            token_amount=params["token_amount"],
            slippage_basis_points=params.get("slippage_basis_points", 100),
            bonding_curve=params["bonding_curve"],
            creator_vault=params["creator_vault"],
            associated_bonding_curve=params["associated_bonding_curve"],
            token_program=params.get("token_program", bytes(32)),
            close_token_account=params.get("close_token_account", False),
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "PumpFun",
            "type": "sell",
        }


class PumpSwapExecutor(TradeExecutor):
    """PumpSwap trade executor"""

    async def execute_buy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on PumpSwap"""
        from ..instruction.pumpswap import PumpSwapInstructionBuilder

        instructions = PumpSwapInstructionBuilder.build_buy_instructions(
            payer=params["payer"],
            pool=params["pool"],
            base_mint=params["base_mint"],
            quote_mint=params["quote_mint"],
            input_amount=params["input_amount"],
            slippage_basis_points=params.get("slippage_basis_points", 100),
            pool_base_token_account=params["pool_base_token_account"],
            pool_quote_token_account=params["pool_quote_token_account"],
            pool_base_token_reserves=params["pool_base_token_reserves"],
            pool_quote_token_reserves=params["pool_quote_token_reserves"],
            coin_creator_vault_ata=params["coin_creator_vault_ata"],
            coin_creator_vault_authority=params["coin_creator_vault_authority"],
            base_token_program=params.get("base_token_program", bytes(32)),
            quote_token_program=params.get("quote_token_program", bytes(32)),
            is_mayhem_mode=params.get("is_mayhem_mode", False),
            is_cashback_coin=params.get("is_cashback_coin", False),
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "PumpSwap",
            "type": "buy",
        }

    async def execute_sell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on PumpSwap"""
        from ..instruction.pumpswap import PumpSwapInstructionBuilder

        instructions = PumpSwapInstructionBuilder.build_sell_instructions(
            payer=params["payer"],
            pool=params["pool"],
            base_mint=params["base_mint"],
            quote_mint=params["quote_mint"],
            token_amount=params["token_amount"],
            slippage_basis_points=params.get("slippage_basis_points", 100),
            pool_base_token_account=params["pool_base_token_account"],
            pool_quote_token_account=params["pool_quote_token_account"],
            pool_base_token_reserves=params["pool_base_token_reserves"],
            pool_quote_token_reserves=params["pool_quote_token_reserves"],
            coin_creator_vault_ata=params["coin_creator_vault_ata"],
            coin_creator_vault_authority=params["coin_creator_vault_authority"],
            base_token_program=params.get("base_token_program", bytes(32)),
            quote_token_program=params.get("quote_token_program", bytes(32)),
            is_mayhem_mode=params.get("is_mayhem_mode", False),
            is_cashback_coin=params.get("is_cashback_coin", False),
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "PumpSwap",
            "type": "sell",
        }


class RaydiumCpmmExecutor(TradeExecutor):
    """Raydium CPMM trade executor"""

    async def execute_buy(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy on Raydium CPMM"""
        from ..instruction.raydium_cpmm import RaydiumCpmmInstructionBuilder

        instructions = RaydiumCpmmInstructionBuilder.build_buy_instructions(
            payer=params["payer"],
            amm_config=params["amm_config"],
            pool_state=params["pool_state"],
            output_mint=params["output_mint"],
            wsol_mint=params.get("wsol_mint", bytes(32)),
            input_token_account=params["input_token_account"],
            output_token_account=params["output_token_account"],
            input_vault=params["input_vault"],
            output_vault=params["output_vault"],
            token_program=params.get("token_program", bytes(32)),
            amount_in=params["amount_in"],
            minimum_amount_out=params["minimum_amount_out"],
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "RaydiumCpmm",
            "type": "buy",
        }

    async def execute_sell(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell on Raydium CPMM"""
        from ..instruction.raydium_cpmm import RaydiumCpmmInstructionBuilder

        instructions = RaydiumCpmmInstructionBuilder.build_sell_instructions(
            payer=params["payer"],
            amm_config=params["amm_config"],
            pool_state=params["pool_state"],
            input_mint=params["input_mint"],
            wsol_mint=params.get("wsol_mint", bytes(32)),
            input_token_account=params["input_token_account"],
            output_token_account=params["output_token_account"],
            input_vault=params["input_vault"],
            output_vault=params["output_vault"],
            token_program=params.get("token_program", bytes(32)),
            amount_in=params["amount_in"],
            minimum_amount_out=params["minimum_amount_out"],
        )

        return {
            "success": True,
            "instructions": instructions,
            "dex": "RaydiumCpmm",
            "type": "sell",
        }


class TradeExecutorFactory:
    """Factory for creating trade executors"""

    _executors = {
        DexType.PUMP_FUN: PumpFunExecutor,
        DexType.PUMP_SWAP: PumpSwapExecutor,
        DexType.RAYDIUM_CPMM: RaydiumCpmmExecutor,
        # Add more executors as needed
    }

    @classmethod
    def create_executor(cls, dex_type: DexType) -> TradeExecutor:
        """Create trade executor for given DEX type"""
        executor_class = cls._executors.get(dex_type)
        if not executor_class:
            raise ValueError(f"No executor available for DEX type: {dex_type}")
        return executor_class()

    @classmethod
    def register_executor(cls, dex_type: DexType, executor_class: type):
        """Register a new executor class"""
        cls._executors[dex_type] = executor_class


class TradingClient:
    """High-level trading client"""

    def __init__(self):
        self.executors: Dict[DexType, TradeExecutor] = {}

    def get_executor(self, dex_type: DexType) -> TradeExecutor:
        """Get or create executor for DEX type"""
        if dex_type not in self.executors:
            self.executors[dex_type] = TradeExecutorFactory.create_executor(dex_type)
        return self.executors[dex_type]

    async def buy(self, dex_type: DexType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute buy trade"""
        executor = self.get_executor(dex_type)
        return await executor.execute_buy(params)

    async def sell(self, dex_type: DexType, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute sell trade"""
        executor = self.get_executor(dex_type)
        return await executor.execute_sell(params)
