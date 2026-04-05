"""
Trading parameters for all DEX protocols.
Based on sol-trade-sdk Rust implementation.
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Union
from enum import Enum, auto


class DexType(Enum):
    """DEX protocol types"""
    PUMP_FUN = "PumpFun"
    PUMP_SWAP = "PumpSwap"
    BONK = "Bonk"
    RAYDIUM_CPMM = "RaydiumCpmm"
    RAYDIUM_AMM_V4 = "RaydiumAmmV4"
    METEORA_DAMM_V2 = "MeteoraDammV2"


class TradeType(Enum):
    """Type of trade operation"""
    BUY = "Buy"
    SELL = "Sell"
    CREATE = "Create"
    CREATE_AND_BUY = "CreateAndBuy"


@dataclass
class PumpFunParams:
    """
    PumpFun protocol specific parameters.

    **Creator Rewards Sharing**: Some coins use a dynamic `creator_vault` (fee-sharing config).
    Always use the latest on-chain creator/vault when building params for **sell**; do not reuse
    cached params from buy.
    """
    bonding_curve: Any = None  # BondingCurveAccount
    associated_bonding_curve: bytes = field(default_factory=lambda: bytes(32))
    creator_vault: bytes = field(default_factory=lambda: bytes(32))
    token_program: bytes = field(default_factory=lambda: bytes(32))
    close_token_account_when_sell: Optional[bool] = None

    @classmethod
    def immediate_sell(
        cls,
        creator_vault: bytes,
        token_program: bytes,
        close_token_account_when_sell: bool = False,
    ) -> "PumpFunParams":
        """Create params for immediate sell"""
        from ..common.bonding_curve import BondingCurveAccount
        return cls(
            bonding_curve=BondingCurveAccount(),
            associated_bonding_curve=bytes(32),
            creator_vault=creator_vault,
            token_program=token_program,
            close_token_account_when_sell=close_token_account_when_sell,
        )

    @classmethod
    def from_dev_trade(
        cls,
        mint: bytes,
        token_amount: int,
        max_sol_cost: int,
        creator: bytes,
        bonding_curve: bytes,
        associated_bonding_curve: bytes,
        creator_vault: bytes,
        close_token_account_when_sell: Optional[bool] = None,
        fee_recipient: bytes = field(default_factory=lambda: bytes(32)),
        token_program: bytes = field(default_factory=lambda: bytes(32)),
        is_cashback_coin: bool = False,
    ) -> "PumpFunParams":
        """Create from dev trade data"""
        from ..common.bonding_curve import BondingCurveAccount
        from ..instruction.pumpfun import MAYHEM_FEE_RECIPIENT

        is_mayhem_mode = fee_recipient == MAYHEM_FEE_RECIPIENT
        bonding_curve_account = BondingCurveAccount.from_dev_trade(
            bonding_curve,
            mint,
            token_amount,
            max_sol_cost,
            creator,
            is_mayhem_mode,
            is_cashback_coin,
        )
        return cls(
            bonding_curve=bonding_curve_account,
            associated_bonding_curve=associated_bonding_curve,
            creator_vault=creator_vault,
            close_token_account_when_sell=close_token_account_when_sell,
            token_program=token_program,
        )

    @classmethod
    def from_trade(
        cls,
        bonding_curve: bytes,
        associated_bonding_curve: bytes,
        mint: bytes,
        creator: bytes,
        creator_vault: bytes,
        virtual_token_reserves: int,
        virtual_sol_reserves: int,
        real_token_reserves: int,
        real_sol_reserves: int,
        close_token_account_when_sell: Optional[bool] = None,
        fee_recipient: bytes = field(default_factory=lambda: bytes(32)),
        token_program: bytes = field(default_factory=lambda: bytes(32)),
        is_cashback_coin: bool = False,
    ) -> "PumpFunParams":
        """Create from trade data"""
        from ..common.bonding_curve import BondingCurveAccount
        from ..instruction.pumpfun import MAYHEM_FEE_RECIPIENT

        is_mayhem_mode = fee_recipient == MAYHEM_FEE_RECIPIENT
        bonding_curve_account = BondingCurveAccount.from_trade(
            bonding_curve,
            mint,
            creator,
            virtual_token_reserves,
            virtual_sol_reserves,
            real_token_reserves,
            real_sol_reserves,
            is_mayhem_mode,
            is_cashback_coin,
        )
        return cls(
            bonding_curve=bonding_curve_account,
            associated_bonding_curve=associated_bonding_curve,
            creator_vault=creator_vault,
            close_token_account_when_sell=close_token_account_when_sell,
            token_program=token_program,
        )

    def with_creator_vault(self, creator_vault: bytes) -> "PumpFunParams":
        """Override creator_vault with a value from gRPC/event"""
        self.creator_vault = creator_vault
        return self


@dataclass
class PumpSwapParams:
    """PumpSwap protocol specific parameters"""
    pool: bytes = field(default_factory=lambda: bytes(32))
    base_mint: bytes = field(default_factory=lambda: bytes(32))
    quote_mint: bytes = field(default_factory=lambda: bytes(32))
    pool_base_token_account: bytes = field(default_factory=lambda: bytes(32))
    pool_quote_token_account: bytes = field(default_factory=lambda: bytes(32))
    pool_base_token_reserves: int = 0
    pool_quote_token_reserves: int = 0
    coin_creator_vault_ata: bytes = field(default_factory=lambda: bytes(32))
    coin_creator_vault_authority: bytes = field(default_factory=lambda: bytes(32))
    base_token_program: bytes = field(default_factory=lambda: bytes(32))
    quote_token_program: bytes = field(default_factory=lambda: bytes(32))
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False

    @classmethod
    def new(
        cls,
        pool: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        pool_base_token_account: bytes,
        pool_quote_token_account: bytes,
        pool_base_token_reserves: int,
        pool_quote_token_reserves: int,
        coin_creator_vault_ata: bytes,
        coin_creator_vault_authority: bytes,
        base_token_program: bytes,
        quote_token_program: bytes,
        fee_recipient: bytes,
        is_cashback_coin: bool = False,
    ) -> "PumpSwapParams":
        """Create new PumpSwapParams"""
        from ..instruction.pumpswap import MAYHEM_FEE_RECIPIENT
        is_mayhem_mode = fee_recipient == MAYHEM_FEE_RECIPIENT
        return cls(
            pool=pool,
            base_mint=base_mint,
            quote_mint=quote_mint,
            pool_base_token_account=pool_base_token_account,
            pool_quote_token_account=pool_quote_token_account,
            pool_base_token_reserves=pool_base_token_reserves,
            pool_quote_token_reserves=pool_quote_token_reserves,
            coin_creator_vault_ata=coin_creator_vault_ata,
            coin_creator_vault_authority=coin_creator_vault_authority,
            base_token_program=base_token_program,
            quote_token_program=quote_token_program,
            is_mayhem_mode=is_mayhem_mode,
            is_cashback_coin=is_cashback_coin,
        )

    @classmethod
    def from_trade(
        cls,
        pool: bytes,
        base_mint: bytes,
        quote_mint: bytes,
        pool_base_token_account: bytes,
        pool_quote_token_account: bytes,
        pool_base_token_reserves: int,
        pool_quote_token_reserves: int,
        coin_creator_vault_ata: bytes,
        coin_creator_vault_authority: bytes,
        base_token_program: bytes,
        quote_token_program: bytes,
        fee_recipient: bytes,
        is_cashback_coin: bool = False,
    ) -> "PumpSwapParams":
        """Create from trade data"""
        return cls.new(
            pool,
            base_mint,
            quote_mint,
            pool_base_token_account,
            pool_quote_token_account,
            pool_base_token_reserves,
            pool_quote_token_reserves,
            coin_creator_vault_ata,
            coin_creator_vault_authority,
            base_token_program,
            quote_token_program,
            fee_recipient,
            is_cashback_coin,
        )


@dataclass
class BonkParams:
    """Bonk protocol specific parameters"""
    virtual_base: int = 0
    virtual_quote: int = 0
    real_base: int = 0
    real_quote: int = 0
    pool_state: bytes = field(default_factory=lambda: bytes(32))
    base_vault: bytes = field(default_factory=lambda: bytes(32))
    quote_vault: bytes = field(default_factory=lambda: bytes(32))
    mint_token_program: bytes = field(default_factory=lambda: bytes(32))
    platform_config: bytes = field(default_factory=lambda: bytes(32))
    platform_associated_account: bytes = field(default_factory=lambda: bytes(32))
    creator_associated_account: bytes = field(default_factory=lambda: bytes(32))
    global_config: bytes = field(default_factory=lambda: bytes(32))

    @classmethod
    def immediate_sell(
        cls,
        mint_token_program: bytes,
        platform_config: bytes,
        platform_associated_account: bytes,
        creator_associated_account: bytes,
        global_config: bytes,
    ) -> "BonkParams":
        """Create params for immediate sell"""
        return cls(
            mint_token_program=mint_token_program,
            platform_config=platform_config,
            platform_associated_account=platform_associated_account,
            creator_associated_account=creator_associated_account,
            global_config=global_config,
        )

    @classmethod
    def from_trade(
        cls,
        virtual_base: int,
        virtual_quote: int,
        real_base_after: int,
        real_quote_after: int,
        pool_state: bytes,
        base_vault: bytes,
        quote_vault: bytes,
        base_token_program: bytes,
        platform_config: bytes,
        platform_associated_account: bytes,
        creator_associated_account: bytes,
        global_config: bytes,
    ) -> "BonkParams":
        """Create from trade data"""
        return cls(
            virtual_base=virtual_base,
            virtual_quote=virtual_quote,
            real_base=real_base_after,
            real_quote=real_quote_after,
            pool_state=pool_state,
            base_vault=base_vault,
            quote_vault=quote_vault,
            mint_token_program=base_token_program,
            platform_config=platform_config,
            platform_associated_account=platform_associated_account,
            creator_associated_account=creator_associated_account,
            global_config=global_config,
        )


@dataclass
class RaydiumCpmmParams:
    """Raydium CPMM protocol specific parameters"""
    pool_state: bytes = field(default_factory=lambda: bytes(32))
    amm_config: bytes = field(default_factory=lambda: bytes(32))
    base_mint: bytes = field(default_factory=lambda: bytes(32))
    quote_mint: bytes = field(default_factory=lambda: bytes(32))
    base_reserve: int = 0
    quote_reserve: int = 0
    base_vault: bytes = field(default_factory=lambda: bytes(32))
    quote_vault: bytes = field(default_factory=lambda: bytes(32))
    base_token_program: bytes = field(default_factory=lambda: bytes(32))
    quote_token_program: bytes = field(default_factory=lambda: bytes(32))
    observation_state: bytes = field(default_factory=lambda: bytes(32))

    @classmethod
    def from_trade(
        cls,
        pool_state: bytes,
        amm_config: bytes,
        input_token_mint: bytes,
        output_token_mint: bytes,
        input_vault: bytes,
        output_vault: bytes,
        input_token_program: bytes,
        output_token_program: bytes,
        observation_state: bytes,
        base_reserve: int,
        quote_reserve: int,
    ) -> "RaydiumCpmmParams":
        """Create from trade data"""
        return cls(
            pool_state=pool_state,
            amm_config=amm_config,
            base_mint=input_token_mint,
            quote_mint=output_token_mint,
            base_reserve=base_reserve,
            quote_reserve=quote_reserve,
            base_vault=input_vault,
            quote_vault=output_vault,
            base_token_program=input_token_program,
            quote_token_program=output_token_program,
            observation_state=observation_state,
        )


@dataclass
class RaydiumAmmV4Params:
    """Raydium AMM V4 protocol specific parameters"""
    amm: bytes = field(default_factory=lambda: bytes(32))
    coin_mint: bytes = field(default_factory=lambda: bytes(32))
    pc_mint: bytes = field(default_factory=lambda: bytes(32))
    token_coin: bytes = field(default_factory=lambda: bytes(32))
    token_pc: bytes = field(default_factory=lambda: bytes(32))
    coin_reserve: int = 0
    pc_reserve: int = 0

    @classmethod
    def new(
        cls,
        amm: bytes,
        coin_mint: bytes,
        pc_mint: bytes,
        token_coin: bytes,
        token_pc: bytes,
        coin_reserve: int,
        pc_reserve: int,
    ) -> "RaydiumAmmV4Params":
        """Create new RaydiumAmmV4Params"""
        return cls(
            amm=amm,
            coin_mint=coin_mint,
            pc_mint=pc_mint,
            token_coin=token_coin,
            token_pc=token_pc,
            coin_reserve=coin_reserve,
            pc_reserve=pc_reserve,
        )


@dataclass
class MeteoraDammV2Params:
    """Meteora Damm V2 protocol specific parameters"""
    pool: bytes = field(default_factory=lambda: bytes(32))
    token_a_vault: bytes = field(default_factory=lambda: bytes(32))
    token_b_vault: bytes = field(default_factory=lambda: bytes(32))
    token_a_mint: bytes = field(default_factory=lambda: bytes(32))
    token_b_mint: bytes = field(default_factory=lambda: bytes(32))
    token_a_program: bytes = field(default_factory=lambda: bytes(32))
    token_b_program: bytes = field(default_factory=lambda: bytes(32))

    @classmethod
    def new(
        cls,
        pool: bytes,
        token_a_vault: bytes,
        token_b_vault: bytes,
        token_a_mint: bytes,
        token_b_mint: bytes,
        token_a_program: bytes,
        token_b_program: bytes,
    ) -> "MeteoraDammV2Params":
        """Create new MeteoraDammV2Params"""
        return cls(
            pool=pool,
            token_a_vault=token_a_vault,
            token_b_vault=token_b_vault,
            token_a_mint=token_a_mint,
            token_b_mint=token_b_mint,
            token_a_program=token_a_program,
            token_b_program=token_b_program,
        )


# Union type for all DEX params
DexParams = Union[
    PumpFunParams,
    PumpSwapParams,
    BonkParams,
    RaydiumCpmmParams,
    RaydiumAmmV4Params,
    MeteoraDammV2Params,
]
