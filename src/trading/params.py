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
        from ..instruction.pumpfun_builder import MAYHEM_FEE_RECIPIENTS

        is_mayhem_mode = bytes(fee_recipient) in {bytes(p) for p in MAYHEM_FEE_RECIPIENTS}
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
        from ..instruction.pumpfun_builder import MAYHEM_FEE_RECIPIENTS

        is_mayhem_mode = bytes(fee_recipient) in {bytes(p) for p in MAYHEM_FEE_RECIPIENTS}
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
class PumpSwapFeeBasisPoints:
    """PumpSwap fee basis points for parser/RPC-provided params."""
    lp_fee_basis_points: int = 25
    protocol_fee_basis_points: int = 5
    coin_creator_fee_basis_points: int = 5


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
    pool_creator: bytes = field(default_factory=lambda: bytes(32))
    coin_creator: bytes = field(default_factory=lambda: bytes(32))
    cashback_fee_basis_points: int = 0
    fee_basis_points: PumpSwapFeeBasisPoints | None = None
    base_mint_supply: int | None = None

    @staticmethod
    def _bytes_to_pubkey(value: bytes):
        from solders.pubkey import Pubkey

        return value if isinstance(value, Pubkey) else Pubkey.from_bytes(bytes(value))

    @staticmethod
    def _pubkey_to_bytes(value: Any) -> bytes:
        return bytes(value)

    @classmethod
    def _from_builder_params(cls, params: Any) -> "PumpSwapParams":
        fee_basis_points = getattr(params, "fee_basis_points", None)
        root_fee_basis_points = (
            PumpSwapFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            )
            if fee_basis_points is not None
            else None
        )
        return cls(
            pool=cls._pubkey_to_bytes(params.pool),
            base_mint=cls._pubkey_to_bytes(params.base_mint),
            quote_mint=cls._pubkey_to_bytes(params.quote_mint),
            pool_base_token_account=cls._pubkey_to_bytes(params.pool_base_token_account),
            pool_quote_token_account=cls._pubkey_to_bytes(params.pool_quote_token_account),
            pool_base_token_reserves=params.pool_base_token_reserves,
            pool_quote_token_reserves=params.pool_quote_token_reserves,
            coin_creator_vault_ata=cls._pubkey_to_bytes(params.coin_creator_vault_ata),
            coin_creator_vault_authority=cls._pubkey_to_bytes(params.coin_creator_vault_authority),
            base_token_program=cls._pubkey_to_bytes(params.base_token_program),
            quote_token_program=cls._pubkey_to_bytes(params.quote_token_program),
            is_mayhem_mode=params.is_mayhem_mode,
            is_cashback_coin=params.is_cashback_coin,
            pool_creator=cls._pubkey_to_bytes(params.pool_creator),
            coin_creator=cls._pubkey_to_bytes(params.coin_creator),
            cashback_fee_basis_points=params.cashback_fee_basis_points,
            fee_basis_points=root_fee_basis_points,
            base_mint_supply=params.base_mint_supply,
        )

    @classmethod
    async def from_pool_address_by_rpc(
        cls,
        fetcher: Any,
        pool_address: bytes,
        fee_basis_points: PumpSwapFeeBasisPoints | None = None,
        cashback_fee_basis_points: int = 0,
    ) -> "PumpSwapParams":
        from ..instruction.pumpswap_builder import (
            PumpSwapFeeBasisPoints as BuilderFeeBasisPoints,
            params_from_pool_address,
        )

        builder_fee_basis_points = (
            BuilderFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            )
            if fee_basis_points is not None
            else None
        )
        params = await params_from_pool_address(
            fetcher,
            cls._bytes_to_pubkey(pool_address),
            fee_basis_points=builder_fee_basis_points,
            cashback_fee_basis_points=cashback_fee_basis_points,
        )
        return cls._from_builder_params(params)

    @classmethod
    async def from_mint_by_rpc(
        cls,
        fetcher: Any,
        mint: bytes,
        fee_basis_points: PumpSwapFeeBasisPoints | None = None,
        cashback_fee_basis_points: int = 0,
    ) -> "PumpSwapParams":
        from ..instruction.pumpswap_builder import (
            PumpSwapFeeBasisPoints as BuilderFeeBasisPoints,
            params_from_mint,
        )

        builder_fee_basis_points = (
            BuilderFeeBasisPoints(
                fee_basis_points.lp_fee_basis_points,
                fee_basis_points.protocol_fee_basis_points,
                fee_basis_points.coin_creator_fee_basis_points,
            )
            if fee_basis_points is not None
            else None
        )
        params = await params_from_mint(
            fetcher,
            cls._bytes_to_pubkey(mint),
            fee_basis_points=builder_fee_basis_points,
            cashback_fee_basis_points=cashback_fee_basis_points,
        )
        return cls._from_builder_params(params)

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
        coin_creator: bytes = bytes(32),
        is_cashback_coin: bool = False,
        cashback_fee_basis_points: int = 0,
        fee_basis_points: PumpSwapFeeBasisPoints | None = None,
    ) -> "PumpSwapParams":
        """Create new PumpSwapParams"""
        from ..instruction.pumpswap_builder import MAYHEM_FEE_RECIPIENTS

        is_mayhem_mode = bytes(fee_recipient) in {bytes(p) for p in MAYHEM_FEE_RECIPIENTS}
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
            coin_creator=coin_creator,
            cashback_fee_basis_points=cashback_fee_basis_points,
            fee_basis_points=fee_basis_points,
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
        coin_creator: bytes = bytes(32),
        is_cashback_coin: bool = False,
        cashback_fee_basis_points: int = 0,
        fee_basis_points: PumpSwapFeeBasisPoints | None = None,
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
            coin_creator,
            is_cashback_coin,
            cashback_fee_basis_points,
            fee_basis_points,
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
    amm_open_orders: bytes = field(default_factory=lambda: bytes(32))
    amm_target_orders: bytes = field(default_factory=lambda: bytes(32))
    serum_program: bytes = field(default_factory=lambda: bytes(32))
    serum_market: bytes = field(default_factory=lambda: bytes(32))
    serum_bids: bytes = field(default_factory=lambda: bytes(32))
    serum_asks: bytes = field(default_factory=lambda: bytes(32))
    serum_event_queue: bytes = field(default_factory=lambda: bytes(32))
    serum_coin_vault_account: bytes = field(default_factory=lambda: bytes(32))
    serum_pc_vault_account: bytes = field(default_factory=lambda: bytes(32))
    serum_vault_signer: bytes = field(default_factory=lambda: bytes(32))
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
        amm_open_orders: bytes,
        amm_target_orders: bytes,
        serum_program: bytes,
        serum_market: bytes,
        serum_bids: bytes,
        serum_asks: bytes,
        serum_event_queue: bytes,
        serum_coin_vault_account: bytes,
        serum_pc_vault_account: bytes,
        serum_vault_signer: bytes,
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
            amm_open_orders=amm_open_orders,
            amm_target_orders=amm_target_orders,
            serum_program=serum_program,
            serum_market=serum_market,
            serum_bids=serum_bids,
            serum_asks=serum_asks,
            serum_event_queue=serum_event_queue,
            serum_coin_vault_account=serum_coin_vault_account,
            serum_pc_vault_account=serum_pc_vault_account,
            serum_vault_signer=serum_vault_signer,
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
