"""
Sol Trade SDK - Python SDK for Solana DEX trading

A comprehensive SDK for seamless Solana DEX trading with support for
PumpFun, PumpSwap, Bonk, Raydium CPMM, Raydium AMM V4, and Meteora DAMM V2.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, replace
import asyncio
import time
import os

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import Transaction
from solders.message import Message, MessageV0
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash as Blockhash
from solders import compute_budget, system_program
from solders.transaction import VersionedTransaction
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed

# ============== Enums ==============


class DexType(Enum):
    """Supported DEX protocols"""

    PUMPFUN = "PumpFun"
    PUMPSWAP = "PumpSwap"
    BONK = "Bonk"
    RAYDIUM_CPMM = "RaydiumCpmm"
    RAYDIUM_AMM_V4 = "RaydiumAmmV4"
    METEORA_DAMM_V2 = "MeteoraDammV2"


class TradeTokenType(Enum):
    """Type of token to trade"""

    SOL = "SOL"
    WSOL = "WSOL"
    USD1 = "USD1"
    USDC = "USDC"


class AccountPolicy(Enum):
    """Account lifecycle policy for high-level trade requests."""

    AUTO = "Auto"
    HOT_PATH_MINIMAL = "HotPathMinimal"
    CREATE_MISSING = "CreateMissing"
    ASSUME_PREPARED = "AssumePrepared"


class TradeType(Enum):
    """Trade operation type"""

    BUY = "Buy"
    SELL = "Sell"


class SwqosRegion(Enum):
    """SWQOS service regions"""

    NEW_YORK = "NewYork"
    FRANKFURT = "Frankfurt"
    AMSTERDAM = "Amsterdam"
    DUBLIN = "Dublin"
    SLC = "SLC"
    TOKYO = "Tokyo"
    LONDON = "London"
    LOS_ANGELES = "LosAngeles"
    SINGAPORE = "Singapore"
    DEFAULT = "Default"


class SwqosType(Enum):
    """SWQOS service types"""

    DEFAULT = "Default"
    JITO = "Jito"
    BLOXROUTE = "Bloxroute"
    ZEROSLOT = "ZeroSlot"
    ZERO_SLOT = "ZeroSlot"
    TEMPORAL = "Temporal"
    FLASHBLOCK = "FlashBlock"
    FLASH_BLOCK = "FlashBlock"
    BLOCKRAZOR = "BlockRazor"
    BLOCK_RAZOR = "BlockRazor"
    NODE1 = "Node1"
    ASTRALANE = "Astralane"
    NEXTBLOCK = "NextBlock"
    NEXT_BLOCK = "NextBlock"
    HELIUS = "Helius"
    STELLIUM = "Stellium"
    LIGHTSPEED = "Lightspeed"
    SOYAS = "Soyas"
    SPEEDLANDING = "Speedlanding"
    SOLAMI = "Solami"


class SwqosTransport(Enum):
    """SWQOS transport mode."""

    HTTP = "Http"
    GRPC = "Grpc"
    QUIC = "Quic"


class AstralaneTransport(Enum):
    """Astralane transport mode."""

    BINARY = "Binary"
    PLAIN = "Plain"
    QUIC = "Quic"


# ============== Constants ==============

# System programs
SYSTEM_PROGRAM = Pubkey.from_string("11111111111111111111111111111111")

# Token programs
TOKEN_PROGRAM = Pubkey.from_string("TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA")
TOKEN_PROGRAM_2022 = Pubkey.from_string("TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb")

# Token mints
SOL_TOKEN_ACCOUNT = Pubkey.from_string("So11111111111111111111111111111111111111111")
WSOL_TOKEN_ACCOUNT = Pubkey.from_string("So11111111111111111111111111111111111111112")
USD1_TOKEN_ACCOUNT = Pubkey.from_string("USD1ttGY1N17NEEHLmELoaybftRBUSErhqYiQzvEmuB")
USDC_TOKEN_ACCOUNT = Pubkey.from_string("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")

# Associated token program
ASSOCIATED_TOKEN_PROGRAM = Pubkey.from_string("ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL")

# Rent sysvar
RENT = Pubkey.from_string("SysvarRent111111111111111111111111111111111")

# DEX Programs
PUMPFUN_PROGRAM = Pubkey.from_string("6EF8rrecthR5Dkzon8Nwu78hRvfCKopJFfWcCzNfXt3D")
PUMPSWAP_PROGRAM = Pubkey.from_string("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwq52pCSbAhL")
BONK_PROGRAM = Pubkey.from_string("bonk2zCzQaobPKMKsM5Rut46yHp3zQD1ntUk8Ld8ARq")
RAYDIUM_CPMM_PROGRAM = Pubkey.from_string("CPMMoo8L3F4NbTUBBfMTm5L2AhwDtLd6P4VeXvgQA2Po")
RAYDIUM_AMM_V4_PROGRAM = Pubkey.from_string("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8")

# Fee recipients
FEE_RECIPIENT = Pubkey.from_string("CebN5WGQ4jvEPvsVU4EoHEpgzq1VV7AbicfhtW4Cs9tM")

# Default values
DEFAULT_SLIPPAGE = 500  # 5%
DEFAULT_COMPUTE_UNITS = 200000
DEFAULT_PRIORITY_FEE = 100000
DEFAULT_TIP_LAMPORTS = 100000
PACKET_DATA_SIZE = 1232


# ============== Data Classes ==============


def _parser_value(source: Any, name: str, default: Any = None) -> Any:
    if source is None:
        return default
    if isinstance(source, dict):
        return source.get(name, default)
    return getattr(source, name, default)


def _pubkey_from_parser(value: Any) -> Pubkey:
    if value is None:
        return Pubkey.default()
    if isinstance(value, Pubkey):
        return value
    text = str(value)
    if not text or text == "11111111111111111111111111111111":
        return Pubkey.default()
    return Pubkey.from_string(text)


@dataclass
class SwqosConfig:
    """SWQOS service configuration"""

    type: SwqosType
    region: SwqosRegion
    api_key: str = ""
    custom_url: Optional[str] = None
    mev_protection: Optional[bool] = None
    transport: Optional[SwqosTransport] = None
    astralane_transport: Optional[AstralaneTransport] = None
    swqos_only: Optional[bool] = None


SWQOS_BLACKLISTED_VALUES = {"NextBlock"}


def is_swqos_type_blacklisted(swqos_type: SwqosType) -> bool:
    return getattr(swqos_type, "value", swqos_type) in SWQOS_BLACKLISTED_VALUES


def _normalize_swqos_configs(rpc_url: str, configs: List[SwqosConfig]) -> List[SwqosConfig]:
    out = list(configs)
    if not any(getattr(c.type, "value", c.type) == "Default" for c in out):
        out.append(SwqosConfig(
            type=SwqosType.DEFAULT,
            region=SwqosRegion.DEFAULT,
            api_key="",
            custom_url=rpc_url,
        ))
    return [c for c in out if not is_swqos_type_blacklisted(c.type)]


@dataclass
class _FlatGasFeeStrategy:
    """Gas fee strategy configuration"""

    buy_priority_fee: int = 100000
    sell_priority_fee: int = 100000
    buy_compute_units: int = 200000
    sell_compute_units: int = 200000
    buy_tip_lamports: int = 100000
    sell_tip_lamports: int = 100000

    def set_global_fee_strategy(
        self,
        buy_priority: int,
        sell_priority: int,
        buy_cu: int,
        sell_cu: int,
        buy_tip: int,
        sell_tip: int,
    ) -> None:
        """Set global fee strategy"""
        self.buy_priority_fee = buy_priority
        self.sell_priority_fee = sell_priority
        self.buy_compute_units = buy_cu
        self.sell_compute_units = sell_cu
        self.buy_tip_lamports = buy_tip
        self.sell_tip_lamports = sell_tip


@dataclass
class DurableNonceInfo:
    """Durable nonce information"""

    nonce_account: Pubkey
    authority: Pubkey
    nonce_hash: str
    recent_blockhash: str


@dataclass
class BondingCurveAccount:
    """Bonding curve account state"""

    discriminator: int
    account: Pubkey
    virtual_token_reserves: int
    virtual_sol_reserves: int
    real_token_reserves: int
    real_sol_reserves: int
    token_total_supply: int
    complete: bool
    creator: Pubkey
    is_mayhem_mode: bool
    is_cashback_coin: bool


@dataclass
class TradeResult:
    """Trade execution result"""

    success: bool
    signatures: List[str]
    error: Optional[str] = None
    timings: List[Dict[str, Any]] = field(default_factory=list)
    simulation: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class BuyAmount:
    """High-level buy sizing intent."""

    kind: str
    amount: int
    output_amount: Optional[int] = None
    max_input_amount: Optional[int] = None

    @classmethod
    def exact_input(cls, amount: int) -> "BuyAmount":
        return cls("ExactInput", amount)

    @classmethod
    def exact_output(cls, output_amount: int, max_input_amount: int) -> "BuyAmount":
        return cls(
            "ExactOutput",
            max_input_amount,
            output_amount=output_amount,
            max_input_amount=max_input_amount,
        )

    @classmethod
    def with_max_input(cls, quote_amount: int) -> "BuyAmount":
        return cls("WithMaxInput", quote_amount)


@dataclass(frozen=True)
class SellAmount:
    """High-level sell sizing intent."""

    kind: str
    amount: int
    output_amount: Optional[int] = None
    max_input_amount: Optional[int] = None

    @classmethod
    def exact_input(cls, amount: int) -> "SellAmount":
        return cls("ExactInput", amount)

    @classmethod
    def exact_output(cls, output_amount: int, max_input_amount: int) -> "SellAmount":
        return cls(
            "ExactOutput",
            max_input_amount,
            output_amount=output_amount,
            max_input_amount=max_input_amount,
        )


# ============== Protocol Params ==============

def _pumpfun_quote_mint_for_layout(quote_mint: Pubkey) -> Pubkey:
    if quote_mint == Pubkey.default() or quote_mint == SOL_TOKEN_ACCOUNT:
        return Pubkey.default()
    return quote_mint


@dataclass
class PumpFunParams:
    """PumpFun protocol parameters"""

    bonding_curve: BondingCurveAccount = field(
        default_factory=lambda: BondingCurveAccount(
            discriminator=0,
            account=Pubkey.default(),
            virtual_token_reserves=0,
            virtual_sol_reserves=0,
            real_token_reserves=0,
            real_sol_reserves=0,
            token_total_supply=0,
            complete=False,
            creator=Pubkey.default(),
            is_mayhem_mode=False,
            is_cashback_coin=False,
        )
    )
    associated_bonding_curve: Pubkey = field(default_factory=Pubkey.default)
    creator_vault: Pubkey = field(default_factory=Pubkey.default)
    token_program: Pubkey = field(default_factory=lambda: TOKEN_PROGRAM)
    close_token_account_when_sell: Optional[bool] = None
    fee_recipient: Pubkey = field(default_factory=Pubkey.default)
    quote_mint: Pubkey = field(default_factory=Pubkey.default)
    observed_trade_creator: Optional[Pubkey] = None
    fee_sharing_creator_vault_if_active: Optional[Pubkey] = None

    @classmethod
    def immediate_sell(
        cls,
        creator_vault: Pubkey,
        token_program: Pubkey,
        close_token_account_when_sell: bool = False,
    ) -> "PumpFunParams":
        """Create params for immediate sell"""
        return cls(
            bonding_curve=BondingCurveAccount(
                discriminator=0,
                account=Pubkey.default(),
                virtual_token_reserves=0,
                virtual_sol_reserves=0,
                real_token_reserves=0,
                real_sol_reserves=0,
                token_total_supply=0,
                complete=False,
                creator=Pubkey.default(),
                is_mayhem_mode=False,
                is_cashback_coin=False,
            ),
            associated_bonding_curve=Pubkey.default(),
            creator_vault=creator_vault,
            token_program=token_program,
            close_token_account_when_sell=close_token_account_when_sell,
        )

    def with_creator_vault(self, vault: Pubkey) -> "PumpFunParams":
        """Override creator vault"""
        self.creator_vault = vault
        return self

    def with_quote_mint(self, quote_mint: Pubkey) -> "PumpFunParams":
        """Set PumpFun quote mint. The instruction layout is selected from this value."""
        self.quote_mint = _pumpfun_quote_mint_for_layout(quote_mint)
        return self

    @classmethod
    def from_trade(
        cls,
        bonding_curve: Pubkey,
        associated_bonding_curve: Pubkey,
        mint: Pubkey,
        quote_mint: Pubkey,
        creator: Pubkey,
        creator_vault: Pubkey,
        virtual_token_reserves: int,
        virtual_quote_reserves: int,
        real_token_reserves: int,
        real_quote_reserves: int,
        close_token_account_when_sell: Optional[bool],
        fee_recipient: Pubkey,
        token_program: Pubkey,
        is_cashback_coin: bool,
        mayhem_mode: Optional[bool],
    ) -> "PumpFunParams":
        """Build PumpFun params from already-decoded trade event fields."""
        return cls(
            bonding_curve=BondingCurveAccount(
                discriminator=0,
                account=bonding_curve,
                virtual_token_reserves=int(virtual_token_reserves),
                virtual_sol_reserves=int(virtual_quote_reserves),
                real_token_reserves=int(real_token_reserves),
                real_sol_reserves=int(real_quote_reserves),
                token_total_supply=0,
                complete=False,
                creator=creator,
                is_mayhem_mode=bool(mayhem_mode) if mayhem_mode is not None else False,
                is_cashback_coin=is_cashback_coin,
            ),
            associated_bonding_curve=associated_bonding_curve,
            creator_vault=creator_vault,
            token_program=token_program,
            close_token_account_when_sell=close_token_account_when_sell,
            fee_recipient=fee_recipient,
            quote_mint=_pumpfun_quote_mint_for_layout(quote_mint),
            observed_trade_creator=creator if creator != Pubkey.default() else None,
        )

    @classmethod
    def from_parser_trade_event(
        cls,
        event: Any,
        close_token_account_when_sell: Optional[bool] = None,
    ) -> "PumpFunParams":
        """Build params from an already-decoded PumpFun trade event object or dict."""
        quote_mint = _pubkey_from_parser(_parser_value(event, "quote_mint"))
        legacy_sol_quote = quote_mint == Pubkey.default() or quote_mint == SOL_TOKEN_ACCOUNT
        missing = object()
        virtual_quote_value = _parser_value(event, "virtual_quote_reserves", missing)
        if legacy_sol_quote or virtual_quote_value is missing:
            virtual_quote_value = _parser_value(event, "virtual_sol_reserves", 0)
        real_quote_value = _parser_value(event, "real_quote_reserves", missing)
        if legacy_sol_quote or real_quote_value is missing:
            real_quote_value = _parser_value(event, "real_sol_reserves", 0)
        virtual_quote_reserves = int(
            virtual_quote_value or 0
        )
        real_quote_reserves = int(real_quote_value or 0)
        return cls.from_trade(
            bonding_curve=_pubkey_from_parser(_parser_value(event, "bonding_curve")),
            associated_bonding_curve=_pubkey_from_parser(
                _parser_value(event, "associated_bonding_curve")
            ),
            mint=_pubkey_from_parser(_parser_value(event, "mint")),
            quote_mint=quote_mint,
            creator=_pubkey_from_parser(_parser_value(event, "creator")),
            creator_vault=_pubkey_from_parser(_parser_value(event, "creator_vault")),
            virtual_token_reserves=int(_parser_value(event, "virtual_token_reserves", 0) or 0),
            virtual_quote_reserves=virtual_quote_reserves,
            real_token_reserves=int(_parser_value(event, "real_token_reserves", 0) or 0),
            real_quote_reserves=real_quote_reserves,
            close_token_account_when_sell=close_token_account_when_sell,
            fee_recipient=_pubkey_from_parser(_parser_value(event, "fee_recipient")),
            token_program=_pubkey_from_parser(_parser_value(event, "token_program")),
            is_cashback_coin=bool(_parser_value(event, "is_cashback_coin", False)),
            mayhem_mode=bool(_parser_value(event, "mayhem_mode", False)),
        )


@dataclass
class PumpSwapFeeBasisPoints:
    """PumpSwap fee basis points for parser/RPC-provided params."""

    lp_fee_basis_points: int = 25
    protocol_fee_basis_points: int = 5
    coin_creator_fee_basis_points: int = 5


@dataclass
class PumpSwapParams:
    """PumpSwap protocol parameters"""

    pool: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    pool_base_token_account: Pubkey
    pool_quote_token_account: Pubkey
    pool_base_token_reserves: int
    pool_quote_token_reserves: int
    coin_creator_vault_ata: Pubkey
    coin_creator_vault_authority: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False
    pool_creator: Pubkey = field(default_factory=Pubkey.default)
    coin_creator: Pubkey = field(default_factory=Pubkey.default)
    cashback_fee_basis_points: int = 0
    fee_basis_points: Optional[PumpSwapFeeBasisPoints] = None
    base_mint_supply: Optional[int] = None

    @staticmethod
    def _from_builder_params(params: Any) -> "PumpSwapParams":
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
        return PumpSwapParams(
            pool=params.pool,
            base_mint=params.base_mint,
            quote_mint=params.quote_mint,
            pool_base_token_account=params.pool_base_token_account,
            pool_quote_token_account=params.pool_quote_token_account,
            pool_base_token_reserves=params.pool_base_token_reserves,
            pool_quote_token_reserves=params.pool_quote_token_reserves,
            coin_creator_vault_ata=params.coin_creator_vault_ata,
            coin_creator_vault_authority=params.coin_creator_vault_authority,
            base_token_program=params.base_token_program,
            quote_token_program=params.quote_token_program,
            is_mayhem_mode=params.is_mayhem_mode,
            is_cashback_coin=params.is_cashback_coin,
            pool_creator=params.pool_creator or Pubkey.default(),
            coin_creator=params.coin_creator or Pubkey.default(),
            cashback_fee_basis_points=params.cashback_fee_basis_points,
            fee_basis_points=root_fee_basis_points,
            base_mint_supply=params.base_mint_supply,
        )

    @classmethod
    async def from_pool_address_by_rpc(
        cls,
        fetcher: Any,
        pool_address: Pubkey,
        fee_basis_points: Optional[PumpSwapFeeBasisPoints] = None,
        cashback_fee_basis_points: int = 0,
    ) -> "PumpSwapParams":
        """Build params from a pool address using explicit cold-path RPC reads.

        `fee_basis_points` is optional. If provided, it is preserved; otherwise
        the helper fetches PumpSwap FeeConfig and mint supply before trading.
        """
        from .instruction.pumpswap_builder import (
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
            pool_address,
            fee_basis_points=builder_fee_basis_points,
            cashback_fee_basis_points=cashback_fee_basis_points,
        )
        return cls._from_builder_params(params)

    @classmethod
    async def from_mint_by_rpc(
        cls,
        fetcher: Any,
        mint: Pubkey,
        fee_basis_points: Optional[PumpSwapFeeBasisPoints] = None,
        cashback_fee_basis_points: int = 0,
    ) -> "PumpSwapParams":
        """Build params from a mint using explicit cold-path RPC reads."""
        from .instruction.pumpswap_builder import (
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
            mint,
            fee_basis_points=builder_fee_basis_points,
            cashback_fee_basis_points=cashback_fee_basis_points,
        )
        return cls._from_builder_params(params)

    @classmethod
    def from_parser_event(cls, event: Any) -> "PumpSwapParams":
        """Build params from an already-decoded PumpSwap trade event object or dict."""
        has_fee_basis_points = any(
            _parser_value(event, name, None) is not None
            for name in (
                "lp_fee_basis_points",
                "protocol_fee_basis_points",
                "coin_creator_fee_basis_points",
            )
        )
        fee_basis_points = (
            PumpSwapFeeBasisPoints(
                int(_parser_value(event, "lp_fee_basis_points", 0) or 0),
                int(_parser_value(event, "protocol_fee_basis_points", 0) or 0),
                int(_parser_value(event, "coin_creator_fee_basis_points", 0) or 0),
            )
            if has_fee_basis_points
            else None
        )
        return cls(
            pool=_pubkey_from_parser(_parser_value(event, "pool")),
            base_mint=_pubkey_from_parser(_parser_value(event, "base_mint")),
            quote_mint=_pubkey_from_parser(_parser_value(event, "quote_mint")),
            pool_base_token_account=_pubkey_from_parser(
                _parser_value(event, "pool_base_token_account")
            ),
            pool_quote_token_account=_pubkey_from_parser(
                _parser_value(event, "pool_quote_token_account")
            ),
            pool_base_token_reserves=int(_parser_value(event, "pool_base_token_reserves", 0) or 0),
            pool_quote_token_reserves=int(_parser_value(event, "pool_quote_token_reserves", 0) or 0),
            coin_creator_vault_ata=_pubkey_from_parser(
                _parser_value(event, "coin_creator_vault_ata")
            ),
            coin_creator_vault_authority=_pubkey_from_parser(
                _parser_value(event, "coin_creator_vault_authority")
            ),
            base_token_program=_pubkey_from_parser(_parser_value(event, "base_token_program")),
            quote_token_program=_pubkey_from_parser(_parser_value(event, "quote_token_program")),
            is_mayhem_mode=bool(_parser_value(event, "is_mayhem_mode", False)),
            is_cashback_coin=bool(_parser_value(event, "is_cashback_coin", False)),
            pool_creator=_pubkey_from_parser(_parser_value(event, "pool_creator")),
            coin_creator=_pubkey_from_parser(
                _parser_value(event, "coin_creator", _parser_value(event, "creator"))
            ),
            cashback_fee_basis_points=int(
                _parser_value(event, "cashback_fee_basis_points", 0) or 0
            ),
            fee_basis_points=fee_basis_points,
        )


@dataclass
class BonkParams:
    """Bonk protocol parameters"""

    virtual_base: int
    virtual_quote: int
    real_base: int
    real_quote: int
    pool_state: Pubkey
    base_vault: Pubkey
    quote_vault: Pubkey
    mint_token_program: Pubkey
    platform_config: Pubkey
    platform_associated_account: Pubkey
    creator_associated_account: Pubkey
    global_config: Pubkey


@dataclass
class RaydiumCpmmParams:
    """Raydium CPMM protocol parameters"""

    pool_state: Pubkey
    amm_config: Pubkey
    base_mint: Pubkey
    quote_mint: Pubkey
    base_reserve: int
    quote_reserve: int
    base_vault: Pubkey
    quote_vault: Pubkey
    base_token_program: Pubkey
    quote_token_program: Pubkey
    observation_state: Pubkey


@dataclass
class RaydiumAmmV4Params:
    """Raydium AMM V4 protocol parameters"""

    amm: Pubkey
    coin_mint: Pubkey
    pc_mint: Pubkey
    token_coin: Pubkey
    token_pc: Pubkey
    amm_open_orders: Pubkey
    amm_target_orders: Pubkey
    serum_program: Pubkey
    serum_market: Pubkey
    serum_bids: Pubkey
    serum_asks: Pubkey
    serum_event_queue: Pubkey
    serum_coin_vault_account: Pubkey
    serum_pc_vault_account: Pubkey
    serum_vault_signer: Pubkey
    coin_reserve: int
    pc_reserve: int


@dataclass
class MeteoraDammV2Params:
    """Meteora DAMM V2 protocol parameters"""

    pool: Pubkey
    token_a_vault: Pubkey
    token_b_vault: Pubkey
    token_a_mint: Pubkey
    token_b_mint: Pubkey
    token_a_program: Pubkey
    token_b_program: Pubkey


# Union type for protocol params
DexParamEnum = Union[
    PumpFunParams,
    PumpSwapParams,
    BonkParams,
    RaydiumCpmmParams,
    RaydiumAmmV4Params,
    MeteoraDammV2Params,
]


# ============== Trade Params ==============


@dataclass
class TradeBuyParams:
    """Buy trade parameters"""

    dex_type: DexType
    input_token_type: TradeTokenType
    mint: Pubkey
    input_token_amount: int
    extension_params: DexParamEnum
    slippage_basis_points: Optional[int] = None
    recent_blockhash: Optional[str] = None
    address_lookup_table_account: Optional[Any] = None
    wait_tx_confirmed: bool = False
    wait_for_all_submits: bool = False
    create_input_token_ata: bool = True
    close_input_token_ata: bool = False
    create_mint_ata: bool = True
    durable_nonce: Optional[DurableNonceInfo] = None
    fixed_output_token_amount: Optional[int] = None
    gas_fee_strategy: Optional[Any] = None
    simulate: bool = False
    use_exact_sol_amount: Optional[bool] = None
    grpc_recv_us: Optional[int] = None


@dataclass
class TradeSellParams:
    """Sell trade parameters"""

    dex_type: DexType
    output_token_type: TradeTokenType
    mint: Pubkey
    input_token_amount: int
    extension_params: DexParamEnum
    slippage_basis_points: Optional[int] = None
    recent_blockhash: Optional[str] = None
    with_tip: bool = True
    address_lookup_table_account: Optional[Any] = None
    wait_tx_confirmed: bool = False
    wait_for_all_submits: bool = False
    create_output_token_ata: bool = False
    close_output_token_ata: bool = False
    close_mint_token_ata: bool = False
    durable_nonce: Optional[DurableNonceInfo] = None
    fixed_output_token_amount: Optional[int] = None
    gas_fee_strategy: Optional[Any] = None
    simulate: bool = False
    grpc_recv_us: Optional[int] = None


@dataclass
class SimpleBuyParams:
    """Simple buy request that describes trade intent instead of low-level ATA flags."""

    dex_type: DexType
    pay_with: TradeTokenType
    mint: Pubkey
    amount: BuyAmount
    extension_params: DexParamEnum
    recent_blockhash: Optional[str] = None
    gas_fee_strategy: Optional[Any] = None
    slippage_basis_points: Optional[int] = None
    account_policy: AccountPolicy = AccountPolicy.AUTO
    address_lookup_table_account: Optional[Any] = None
    wait_tx_confirmed: bool = False
    wait_for_all_submits: bool = False
    durable_nonce: Optional[DurableNonceInfo] = None
    simulate: bool = False
    grpc_recv_us: Optional[int] = None

    @classmethod
    def new(
        cls,
        dex_type: DexType,
        pay_with: TradeTokenType,
        mint: Pubkey,
        amount: BuyAmount,
        extension_params: DexParamEnum,
        recent_blockhash: str,
        gas_fee_strategy: Optional[Any] = None,
    ) -> "SimpleBuyParams":
        return cls(
            dex_type=dex_type,
            pay_with=pay_with,
            mint=mint,
            amount=amount,
            extension_params=extension_params,
            recent_blockhash=recent_blockhash,
            gas_fee_strategy=gas_fee_strategy,
            account_policy=AccountPolicy.AUTO,
            wait_tx_confirmed=False,
            wait_for_all_submits=False,
            simulate=False,
        )

    @classmethod
    def with_durable_nonce(
        cls,
        dex_type: DexType,
        pay_with: TradeTokenType,
        mint: Pubkey,
        amount: BuyAmount,
        extension_params: DexParamEnum,
        durable_nonce: DurableNonceInfo,
        gas_fee_strategy: Optional[Any] = None,
    ) -> "SimpleBuyParams":
        return cls.new(
            dex_type=dex_type,
            pay_with=pay_with,
            mint=mint,
            amount=amount,
            extension_params=extension_params,
            recent_blockhash="",
            gas_fee_strategy=gas_fee_strategy,
        ).set_durable_nonce(durable_nonce)

    def set_slippage_basis_points(self, value: int) -> "SimpleBuyParams":
        return replace(self, slippage_basis_points=value)

    def set_account_policy(self, value: AccountPolicy) -> "SimpleBuyParams":
        return replace(self, account_policy=value)

    def set_address_lookup_table_account(self, value: Any) -> "SimpleBuyParams":
        return replace(self, address_lookup_table_account=value)

    def set_durable_nonce(self, value: DurableNonceInfo) -> "SimpleBuyParams":
        return replace(self, durable_nonce=value, recent_blockhash=None)

    def set_wait_tx_confirmed(self, value: bool) -> "SimpleBuyParams":
        return replace(self, wait_tx_confirmed=value)

    def set_wait_for_all_submits(self, value: bool) -> "SimpleBuyParams":
        return replace(self, wait_for_all_submits=value)

    def set_simulate(self, value: bool) -> "SimpleBuyParams":
        return replace(self, simulate=value)

    def set_grpc_recv_us(self, value: int) -> "SimpleBuyParams":
        return replace(self, grpc_recv_us=value)


@dataclass
class SimpleSellParams:
    """Simple sell request that describes trade intent instead of low-level ATA flags."""

    dex_type: DexType
    receive_as: TradeTokenType
    mint: Pubkey
    amount: SellAmount
    extension_params: DexParamEnum
    recent_blockhash: Optional[str] = None
    gas_fee_strategy: Optional[Any] = None
    slippage_basis_points: Optional[int] = None
    account_policy: AccountPolicy = AccountPolicy.AUTO
    address_lookup_table_account: Optional[Any] = None
    wait_tx_confirmed: bool = False
    wait_for_all_submits: bool = False
    durable_nonce: Optional[DurableNonceInfo] = None
    simulate: bool = False
    with_tip: bool = True
    grpc_recv_us: Optional[int] = None

    @classmethod
    def new(
        cls,
        dex_type: DexType,
        receive_as: TradeTokenType,
        mint: Pubkey,
        amount: SellAmount,
        extension_params: DexParamEnum,
        recent_blockhash: str,
        gas_fee_strategy: Optional[Any] = None,
    ) -> "SimpleSellParams":
        return cls(
            dex_type=dex_type,
            receive_as=receive_as,
            mint=mint,
            amount=amount,
            extension_params=extension_params,
            recent_blockhash=recent_blockhash,
            gas_fee_strategy=gas_fee_strategy,
            account_policy=AccountPolicy.AUTO,
            wait_tx_confirmed=False,
            wait_for_all_submits=False,
            simulate=False,
            with_tip=True,
        )

    @classmethod
    def with_durable_nonce(
        cls,
        dex_type: DexType,
        receive_as: TradeTokenType,
        mint: Pubkey,
        amount: SellAmount,
        extension_params: DexParamEnum,
        durable_nonce: DurableNonceInfo,
        gas_fee_strategy: Optional[Any] = None,
    ) -> "SimpleSellParams":
        return cls.new(
            dex_type=dex_type,
            receive_as=receive_as,
            mint=mint,
            amount=amount,
            extension_params=extension_params,
            recent_blockhash="",
            gas_fee_strategy=gas_fee_strategy,
        ).set_durable_nonce(durable_nonce)

    def set_slippage_basis_points(self, value: int) -> "SimpleSellParams":
        return replace(self, slippage_basis_points=value)

    def set_account_policy(self, value: AccountPolicy) -> "SimpleSellParams":
        return replace(self, account_policy=value)

    def set_address_lookup_table_account(self, value: Any) -> "SimpleSellParams":
        return replace(self, address_lookup_table_account=value)

    def set_durable_nonce(self, value: DurableNonceInfo) -> "SimpleSellParams":
        return replace(self, durable_nonce=value, recent_blockhash=None)

    def set_wait_tx_confirmed(self, value: bool) -> "SimpleSellParams":
        return replace(self, wait_tx_confirmed=value)

    def set_wait_for_all_submits(self, value: bool) -> "SimpleSellParams":
        return replace(self, wait_for_all_submits=value)

    def set_simulate(self, value: bool) -> "SimpleSellParams":
        return replace(self, simulate=value)

    def set_with_tip(self, value: bool) -> "SimpleSellParams":
        return replace(self, with_tip=value)

    def set_grpc_recv_us(self, value: int) -> "SimpleSellParams":
        return replace(self, grpc_recv_us=value)


# ============== Main Client ==============


@dataclass
class TradeConfig:
    """Trading configuration"""

    rpc_url: str
    swqos_configs: List[SwqosConfig] = field(default_factory=list)
    commitment: Commitment = Confirmed
    log_enabled: bool = True
    check_min_tip: bool = False
    # MEV protection: when enabled, BlockRazor uses sandwichMitigation mode,
    # Astralane uses port 9000 (MEV-protected QUIC endpoint)
    mev_protection: bool = False
    use_seed_optimize: bool = True
    create_wsol_ata_on_startup: bool = True
    swqos_cores_from_end: bool = False
    max_swqos_submit_concurrency: Optional[int] = None
    middleware_manager: Optional[Any] = None

    def __post_init__(self) -> None:
        self.swqos_configs = _normalize_swqos_configs(self.rpc_url, self.swqos_configs)

    @classmethod
    def builder(cls, rpc_url: str) -> "TradeConfigBuilder":
        """Create a TradeConfigBuilder for fluent configuration."""
        return TradeConfigBuilder(rpc_url)


class TradeConfigBuilder:
    """
    Builder for TradeConfig - makes all options discoverable via IDE autocomplete.

    Example::

        config = (
            TradeConfig.builder("https://api.mainnet-beta.solana.com")
            .swqos_configs([
                SwqosConfig(type=SwqosType.JITO, uuid="your_uuid", region=SwqosRegion.FRANKFURT),
                SwqosConfig(type=SwqosType.BLOCKRAZOR, api_token="your_token"),
            ])
            # .log_enabled(False)       # disable logging
            # .check_min_tip(True)      # enforce minimum tip check
            # .mev_protection(True)     # enable MEV protection (sandwichMitigation / port 9000)
            .build()
        )
    """

    def __init__(self, rpc_url: str):
        self._rpc_url = rpc_url
        self._swqos_configs: List[SwqosConfig] = []
        self._commitment: Commitment = Confirmed
        self._log_enabled: bool = True
        self._check_min_tip: bool = False
        self._mev_protection: bool = False
        self._use_seed_optimize: bool = True
        self._create_wsol_ata_on_startup: bool = True
        self._swqos_cores_from_end: bool = False
        self._max_swqos_submit_concurrency: Optional[int] = None
        self._middleware_manager: Optional[Any] = None

    def swqos_configs(self, configs: List[SwqosConfig]) -> "TradeConfigBuilder":
        """Set SWQOS provider configurations."""
        self._swqos_configs = _normalize_swqos_configs(self._rpc_url, configs)
        return self

    def commitment(self, commitment: Commitment) -> "TradeConfigBuilder":
        """Set RPC commitment level (default: Confirmed)."""
        self._commitment = commitment
        return self

    def log_enabled(self, enabled: bool) -> "TradeConfigBuilder":
        """Enable or disable SDK logging (default: True)."""
        self._log_enabled = enabled
        return self

    def check_min_tip(self, enabled: bool) -> "TradeConfigBuilder":
        """Enable minimum tip enforcement (default: False)."""
        self._check_min_tip = enabled
        return self

    def mev_protection(self, enabled: bool) -> "TradeConfigBuilder":
        """
        Enable MEV protection (default: False).

        When enabled:
        - BlockRazor uses ``mode=sandwichMitigation`` (skips sandwich-attack Leaders)
        - Astralane uses port 9000 MEV-protected QUIC endpoint

        Note: Do NOT use durable nonce together with sandwichMitigation mode,
        as it would break the sandwich protection logic.
        """
        self._mev_protection = enabled
        return self

    def use_seed_optimize(self, enabled: bool) -> "TradeConfigBuilder":
        self._use_seed_optimize = enabled
        return self

    def create_wsol_ata_on_startup(self, enabled: bool) -> "TradeConfigBuilder":
        self._create_wsol_ata_on_startup = enabled
        return self

    def swqos_cores_from_end(self, enabled: bool) -> "TradeConfigBuilder":
        self._swqos_cores_from_end = enabled
        return self

    def max_swqos_submit_concurrency(self, limit: Optional[int]) -> "TradeConfigBuilder":
        self._max_swqos_submit_concurrency = limit
        return self

    def middleware_manager(self, manager: Any) -> "TradeConfigBuilder":
        """Set a Rust-style middleware manager."""
        self._middleware_manager = manager
        return self

    def build(self) -> "TradeConfig":
        """Build and return the TradeConfig."""
        return TradeConfig(
            rpc_url=self._rpc_url,
            swqos_configs=self._swqos_configs,
            commitment=self._commitment,
            log_enabled=self._log_enabled,
            check_min_tip=self._check_min_tip,
            mev_protection=self._mev_protection,
            use_seed_optimize=self._use_seed_optimize,
            create_wsol_ata_on_startup=self._create_wsol_ata_on_startup,
            swqos_cores_from_end=self._swqos_cores_from_end,
            max_swqos_submit_concurrency=self._max_swqos_submit_concurrency,
            middleware_manager=self._middleware_manager,
        )


def recommended_sender_thread_core_indices(
    swqos_count: int,
    available_cores: Optional[int] = None,
    from_end: bool = True,
) -> List[int]:
    """Return Rust-parity SWQOS sender core indices."""
    cores = available_cores or os.cpu_count() or 0
    if swqos_count <= 0 or cores <= 0:
        return []
    count = min(swqos_count, max(cores * 2 // 3, 1), cores)
    if from_end:
        return list(range(cores - count, cores))
    return list(range(count))


def _buy_account_flags(policy: AccountPolicy) -> tuple[bool, bool, bool]:
    if policy in (AccountPolicy.HOT_PATH_MINIMAL, AccountPolicy.ASSUME_PREPARED):
        return False, False, False
    if policy == AccountPolicy.CREATE_MISSING:
        return True, True, False
    return False, True, False


def _sell_account_flags(policy: AccountPolicy, receive_as: TradeTokenType) -> tuple[bool, bool, bool]:
    if policy in (AccountPolicy.HOT_PATH_MINIMAL, AccountPolicy.ASSUME_PREPARED):
        return False, False, False
    if policy == AccountPolicy.CREATE_MISSING:
        return True, False, False
    return receive_as != TradeTokenType.SOL, False, False


def simple_buy_params_to_trade_buy_params(params: SimpleBuyParams) -> TradeBuyParams:
    """Convert high-level SimpleBuyParams to legacy TradeBuyParams."""
    fixed_output_token_amount: Optional[int] = None
    if params.amount.kind == "ExactInput":
        input_token_amount = params.amount.amount
        use_exact_sol_amount = True
    elif params.amount.kind == "ExactOutput":
        input_token_amount = params.amount.max_input_amount or params.amount.amount
        fixed_output_token_amount = params.amount.output_amount
        use_exact_sol_amount = True
    elif params.amount.kind == "WithMaxInput":
        input_token_amount = params.amount.amount
        use_exact_sol_amount = False
    else:
        raise ValueError(f"unsupported BuyAmount kind: {params.amount.kind}")

    create_input, create_mint, close_input = _buy_account_flags(params.account_policy)
    return TradeBuyParams(
        dex_type=params.dex_type,
        input_token_type=params.pay_with,
        mint=params.mint,
        input_token_amount=input_token_amount,
        extension_params=params.extension_params,
        slippage_basis_points=params.slippage_basis_points,
        recent_blockhash=None if params.durable_nonce else params.recent_blockhash,
        address_lookup_table_account=params.address_lookup_table_account,
        wait_tx_confirmed=params.wait_tx_confirmed,
        wait_for_all_submits=params.wait_for_all_submits,
        create_input_token_ata=create_input,
        close_input_token_ata=close_input,
        create_mint_ata=create_mint,
        durable_nonce=params.durable_nonce,
        fixed_output_token_amount=fixed_output_token_amount,
        gas_fee_strategy=params.gas_fee_strategy,
        simulate=params.simulate,
        use_exact_sol_amount=use_exact_sol_amount,
        grpc_recv_us=params.grpc_recv_us,
    )


def simple_sell_params_to_trade_sell_params(params: SimpleSellParams) -> TradeSellParams:
    """Convert high-level SimpleSellParams to legacy TradeSellParams."""
    fixed_output_token_amount: Optional[int] = None
    if params.amount.kind == "ExactInput":
        input_token_amount = params.amount.amount
    elif params.amount.kind == "ExactOutput":
        input_token_amount = params.amount.max_input_amount or params.amount.amount
        fixed_output_token_amount = params.amount.output_amount
    else:
        raise ValueError(f"unsupported SellAmount kind: {params.amount.kind}")

    create_output, close_output, close_mint = _sell_account_flags(
        params.account_policy, params.receive_as
    )
    return TradeSellParams(
        dex_type=params.dex_type,
        output_token_type=params.receive_as,
        mint=params.mint,
        input_token_amount=input_token_amount,
        extension_params=params.extension_params,
        slippage_basis_points=params.slippage_basis_points,
        recent_blockhash=None if params.durable_nonce else params.recent_blockhash,
        with_tip=params.with_tip,
        address_lookup_table_account=params.address_lookup_table_account,
        wait_tx_confirmed=params.wait_tx_confirmed,
        wait_for_all_submits=params.wait_for_all_submits,
        create_output_token_ata=create_output,
        close_output_token_ata=close_output,
        close_mint_token_ata=close_mint,
        durable_nonce=params.durable_nonce,
        fixed_output_token_amount=fixed_output_token_amount,
        gas_fee_strategy=params.gas_fee_strategy,
        simulate=params.simulate,
        grpc_recv_us=params.grpc_recv_us,
    )


class TradingClient:
    """Main trading client for Solana DEX operations"""

    def __init__(self, payer: Keypair, config: TradeConfig):
        """
        Initialize trading client.

        Args:
            payer: Keypair for signing transactions
            config: Trading configuration
        """
        self.payer = payer
        self.config = config
        self.client = AsyncClient(config.rpc_url, commitment=config.commitment)
        self.middlewares: List[Any] = []
        self.log_enabled = config.log_enabled
        self.middleware_manager = config.middleware_manager

    async def close(self) -> None:
        """Close the client connection"""
        await self.client.close()

    async def __aenter__(self) -> "TradingClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    def get_payer(self) -> Pubkey:
        """Get the payer public key"""
        return self.payer.pubkey()

    def add_middleware(self, middleware: Any) -> "TradingClient":
        """Add middleware to the chain"""
        self.middlewares.append(middleware)
        return self

    def with_middleware_manager(self, middleware_manager: Any) -> "TradingClient":
        """Attach a Rust-style middleware manager to this client."""
        self.middleware_manager = middleware_manager
        return self

    def _apply_protocol_middlewares(
        self,
        instructions: List[Instruction],
        dex_type: DexType,
        is_buy: bool,
    ) -> List[Instruction]:
        if self.middleware_manager is not None:
            instructions = self.middleware_manager.apply_middlewares_process_protocol_instructions(
                instructions,
                dex_type.value,
                is_buy,
            )
        return instructions

    def _apply_full_middlewares(
        self,
        instructions: List[Instruction],
        trade_type: TradeType,
        dex_type: Optional[DexType] = None,
    ) -> List[Instruction]:
        if self.middleware_manager is not None and dex_type is not None:
            instructions = self.middleware_manager.apply_middlewares_process_full_instructions(
                instructions,
                dex_type.value,
                getattr(trade_type, "value", trade_type) == "Buy",
            )
        return instructions

    def _gas_for_trade(
        self,
        trade_type: TradeType,
        gas_fee_strategy: Optional[Any],
    ) -> tuple[int, int, int]:
        gas = gas_fee_strategy or _FlatGasFeeStrategy()
        trade_value = getattr(trade_type, "value", trade_type)
        if hasattr(gas, "buy_priority_fee"):
            if trade_value == "Buy":
                return gas.buy_priority_fee, gas.buy_compute_units, gas.buy_tip_lamports
            return gas.sell_priority_fee, gas.sell_compute_units, gas.sell_tip_lamports

        try:
            from .common.types import (
                GasFeeStrategyType as CommonGasFeeStrategyType,
                SwqosType as CommonSwqosType,
                TradeType as CommonTradeType,
            )

            common_trade_type = (
                CommonTradeType.BUY if trade_value == "Buy" else CommonTradeType.SELL
            )
            value = gas.get(
                CommonSwqosType.DEFAULT,
                common_trade_type,
                CommonGasFeeStrategyType.NORMAL,
            )
            if value is not None:
                return value.cu_price, value.cu_limit, int(value.tip * 1_000_000_000)
        except Exception:
            pass

        if trade_value == "Buy":
            return gas.buy_priority_fee, gas.buy_compute_units, gas.buy_tip_lamports
        return gas.sell_priority_fee, gas.sell_compute_units, gas.sell_tip_lamports

    def _build_wired_instructions(
        self,
        instructions: List[Instruction],
        trade_type: TradeType,
        gas_fee_strategy: Optional[Any],
        with_tip: bool,
        durable_nonce: Optional[DurableNonceInfo],
        dex_type: Optional[DexType] = None,
        tip_recipient: Optional[Pubkey] = None,
    ) -> List[Instruction]:
        out: List[Instruction] = []
        if durable_nonce:
            out.append(system_program.advance_nonce_account(
                system_program.AdvanceNonceAccountParams(
                    nonce_pubkey=durable_nonce.nonce_account,
                    authorized_pubkey=durable_nonce.authority,
                )
            ))

        unit_price, unit_limit, tip_lamports = self._gas_for_trade(trade_type, gas_fee_strategy)
        if with_tip and tip_recipient is not None and tip_lamports > 0:
            out.append(system_program.transfer(
                system_program.TransferParams(
                    from_pubkey=self.payer.pubkey(),
                    to_pubkey=tip_recipient,
                    lamports=tip_lamports,
                )
            ))

        if unit_price > 0:
            out.append(compute_budget.set_compute_unit_price(unit_price))
        if unit_limit > 0:
            out.append(compute_budget.set_compute_unit_limit(unit_limit))
        out.extend(instructions)
        return self._apply_full_middlewares(out, trade_type, dex_type)

    def _build_transaction(
        self,
        instructions: List[Instruction],
        blockhash: str,
        address_lookup_table_account: Optional[Any],
    ) -> Union[Transaction, VersionedTransaction]:
        parsed_blockhash = Blockhash.from_string(blockhash)
        lookup_tables = []
        if address_lookup_table_account is not None:
            lookup_tables = [address_lookup_table_account]
        if lookup_tables:
            message = MessageV0.try_compile(
                self.payer.pubkey(),
                instructions,
                lookup_tables,
                parsed_blockhash,
            )
            transaction = VersionedTransaction(message, [self.payer])
            serialized_len = len(bytes(transaction))
            if serialized_len > PACKET_DATA_SIZE:
                raise ValueError(
                    f"transaction too large: {serialized_len} > {PACKET_DATA_SIZE}; SDK did not remove compute budget or relay tip because that changes transaction priority semantics. Use an address lookup table or pre-create token ATAs before submitting"
                )
            return transaction

        message = Message.new_with_blockhash(
            instructions, self.payer.pubkey(), parsed_blockhash
        )
        transaction = Transaction.new_unsigned(message)
        transaction.sign([self.payer], parsed_blockhash)
        serialized_len = len(bytes(transaction))
        if serialized_len > PACKET_DATA_SIZE:
            raise ValueError(
                f"transaction too large: {serialized_len} > {PACKET_DATA_SIZE}; SDK did not remove compute budget or relay tip because that changes transaction priority semantics. Use an address lookup table or pre-create token ATAs before submitting"
            )
        return transaction

    async def get_latest_blockhash(self) -> Blockhash:
        """Get latest blockhash"""
        response = await self.client.get_latest_blockhash()
        return response.value

    async def buy(self, params: TradeBuyParams) -> TradeResult:
        """
        Execute a buy order.

        Args:
            params: Buy trade parameters

        Returns:
            TradeResult with transaction details
        """
        if not params.recent_blockhash and not params.durable_nonce:
            return TradeResult(
                success=False,
                signatures=[],
                error="Must provide either recent_blockhash or durable_nonce",
            )

        protocol_params = params.extension_params

        # Build instructions
        builder = self._create_instruction_builder(params.dex_type)
        buy_kwargs = dict(
            payer=self.payer.pubkey(),
            input_mint=self._get_input_mint(params.input_token_type),
            output_mint=params.mint,
            input_amount=params.input_token_amount,
            slippage_basis_points=params.slippage_basis_points or DEFAULT_SLIPPAGE,
            protocol_params=protocol_params,
            create_output_ata=params.create_mint_ata,
            close_input_ata=params.close_input_token_ata,
        )
        if params.dex_type == DexType.PUMPFUN:
            buy_kwargs.update(
                create_input_ata=params.create_input_token_ata,
                fixed_output_amount=params.fixed_output_token_amount,
                use_exact_sol_amount=params.use_exact_sol_amount
                if params.use_exact_sol_amount is not None
                else True,
            )
        elif params.dex_type in (
            DexType.RAYDIUM_CPMM,
            DexType.RAYDIUM_AMM_V4,
            DexType.METEORA_DAMM_V2,
        ):
            buy_kwargs.update(
                create_input_ata=params.create_input_token_ata,
                fixed_output_amount=params.fixed_output_token_amount,
            )
        instructions = await builder.build_buy_instructions(**buy_kwargs)
        instructions = self._apply_protocol_middlewares(
            instructions,
            params.dex_type,
            True,
        )

        # Process middlewares
        for middleware in self.middlewares:
            instructions = await middleware.process(instructions)

        # Execute transaction
        return await self._execute_transaction(
            instructions,
            params.recent_blockhash,
            params.wait_tx_confirmed,
            trade_type=TradeType.BUY,
            address_lookup_table_account=params.address_lookup_table_account,
            durable_nonce=params.durable_nonce,
            gas_fee_strategy=params.gas_fee_strategy,
            simulate=params.simulate,
            with_tip=True,
            dex_type=params.dex_type,
            wait_for_all_submits=params.wait_for_all_submits,
        )

    async def buy_simple(self, params: SimpleBuyParams) -> TradeResult:
        """Execute a high-level buy request."""
        return await self.buy(simple_buy_params_to_trade_buy_params(params))

    async def sell(self, params: TradeSellParams) -> TradeResult:
        """
        Execute a sell order.

        Args:
            params: Sell trade parameters

        Returns:
            TradeResult with transaction details
        """
        if not params.recent_blockhash and not params.durable_nonce:
            return TradeResult(
                success=False,
                signatures=[],
                error="Must provide either recent_blockhash or durable_nonce",
            )

        protocol_params = params.extension_params

        builder = self._create_instruction_builder(params.dex_type)
        sell_kwargs = dict(
            payer=self.payer.pubkey(),
            input_mint=params.mint,
            output_mint=self._get_output_mint(params.output_token_type),
            input_amount=params.input_token_amount,
            slippage_basis_points=params.slippage_basis_points or DEFAULT_SLIPPAGE,
            protocol_params=protocol_params,
            create_output_ata=params.create_output_token_ata,
            close_output_ata=params.close_output_token_ata,
            close_input_ata=params.close_mint_token_ata,
        )
        if params.dex_type == DexType.PUMPFUN:
            sell_kwargs.update(
                fixed_output_amount=params.fixed_output_token_amount,
            )
        elif params.dex_type in (
            DexType.RAYDIUM_CPMM,
            DexType.RAYDIUM_AMM_V4,
            DexType.METEORA_DAMM_V2,
        ):
            sell_kwargs.update(
                fixed_output_amount=params.fixed_output_token_amount,
            )
        instructions = await builder.build_sell_instructions(**sell_kwargs)
        instructions = self._apply_protocol_middlewares(
            instructions,
            params.dex_type,
            False,
        )

        for middleware in self.middlewares:
            instructions = await middleware.process(instructions)

        return await self._execute_transaction(
            instructions,
            params.recent_blockhash,
            params.wait_tx_confirmed,
            trade_type=TradeType.SELL,
            address_lookup_table_account=params.address_lookup_table_account,
            durable_nonce=params.durable_nonce,
            gas_fee_strategy=params.gas_fee_strategy,
            simulate=params.simulate,
            with_tip=params.with_tip,
            dex_type=params.dex_type,
            wait_for_all_submits=params.wait_for_all_submits,
        )

    async def sell_simple(self, params: SimpleSellParams) -> TradeResult:
        """Execute a high-level sell request."""
        return await self.sell(simple_sell_params_to_trade_sell_params(params))

    async def sell_by_percent(
        self, params: TradeSellParams, total_amount: int, percent: int
    ) -> TradeResult:
        """
        Execute a sell order for a percentage of tokens.

        Args:
            params: Sell trade parameters
            total_amount: Total token amount
            percent: Percentage to sell (1-100)

        Returns:
            TradeResult with transaction details
        """
        if percent <= 0 or percent > 100:
            return TradeResult(
                success=False,
                signatures=[],
                error="Percentage must be between 1 and 100",
            )

        amount = total_amount * percent // 100
        params.input_token_amount = amount
        return await self.sell(params)

    async def wrap_sol_to_wsol(self, amount: int) -> str:
        """Wrap SOL to WSOL"""
        if amount <= 0:
            raise ValueError("amount must be greater than zero")

        from .common.wsol_manager import handle_wsol

        return await self._send_instructions_or_raise(
            handle_wsol(self.payer.pubkey(), amount),
            "wrap_sol_to_wsol",
        )

    async def close_wsol(self) -> str:
        """Close WSOL account and unwrap to SOL"""
        from .common.wsol_manager import close_wsol

        return await self._send_instructions_or_raise(
            [close_wsol(self.payer.pubkey())],
            "close_wsol",
        )

    async def _send_instructions_or_raise(
        self,
        instructions: List[Instruction],
        operation: str,
    ) -> str:
        blockhash = str(await self.get_latest_blockhash())
        result = await self._execute_transaction(instructions, blockhash, False)
        if not result.success or not result.signatures:
            raise RuntimeError(result.error or f"{operation} failed")
        return result.signatures[0]

    def _get_input_mint(self, token_type: TradeTokenType) -> Pubkey:
        """Get input mint for token type"""
        mapping = {
            TradeTokenType.SOL: SOL_TOKEN_ACCOUNT,
            TradeTokenType.WSOL: WSOL_TOKEN_ACCOUNT,
            TradeTokenType.USDC: USDC_TOKEN_ACCOUNT,
            TradeTokenType.USD1: USD1_TOKEN_ACCOUNT,
        }
        return mapping[token_type]

    def _get_output_mint(self, token_type: TradeTokenType) -> Pubkey:
        """Get output mint for token type"""
        return self._get_input_mint(token_type)

    def _create_instruction_builder(self, dex_type: DexType):
        """Create instruction builder for DEX type"""
        # Import builders lazily to avoid circular imports
        from .instruction import InstructionBuilderFactory

        return InstructionBuilderFactory.create(dex_type)

    async def _execute_transaction(
        self,
        instructions: List[Instruction],
        blockhash: Optional[str],
        wait_confirmed: bool,
        trade_type: TradeType = TradeType.BUY,
        address_lookup_table_account: Optional[Any] = None,
        durable_nonce: Optional[DurableNonceInfo] = None,
        gas_fee_strategy: Optional[Any] = None,
        simulate: bool = False,
        with_tip: bool = False,
        dex_type: Optional[DexType] = None,
        tip_recipient: Optional[Pubkey] = None,
        wait_for_all_submits: bool = False,
    ) -> TradeResult:
        """Execute transaction with instructions"""
        try:
            effective_blockhash = (durable_nonce.nonce_hash if durable_nonce else None) or blockhash
            if effective_blockhash is None:
                return TradeResult(
                    success=False,
                    signatures=[],
                    error="recent_blockhash or durable_nonce.nonce_hash is required; trade execution hot path does not query RPC for blockhash",
                )

            wired_instructions = self._build_wired_instructions(
                instructions,
                trade_type,
                gas_fee_strategy,
                with_tip,
                durable_nonce,
                dex_type,
                tip_recipient,
            )
            transaction = self._build_transaction(
                wired_instructions,
                effective_blockhash,
                address_lookup_table_account,
            )

            if simulate:
                sim = await self.client.simulate_transaction(
                    transaction,
                    sig_verify=False,
                    commitment=Commitment("processed"),
                )
                value = sim.value
                err = value.err
                return TradeResult(
                    success=err is None,
                    signatures=[],
                    error=f"Simulation failed: {err}" if err is not None else None,
                    simulation={
                        "units_consumed": value.units_consumed,
                        "logs": value.logs,
                    },
                )

            configured_swqos = self.config.swqos_configs or []
            has_non_default_swqos = any(
                getattr(cfg.type, "value", cfg.type) != "Default"
                for cfg in configured_swqos
            )
            if has_non_default_swqos and not with_tip:
                swqos_configs = [
                    cfg
                    for cfg in configured_swqos
                    if getattr(cfg.type, "value", cfg.type) == "Default"
                ]
            else:
                swqos_configs = configured_swqos if has_non_default_swqos else []
            if swqos_configs:
                from .swqos.clients import ClientFactory as SwqosClientFactory, SwqosConfig as SenderSwqosConfig

                non_default_count = sum(
                    1
                    for cfg in swqos_configs
                    if getattr(cfg.type, "value", cfg.type) != "Default"
                )
                if non_default_count > 1 and durable_nonce is None:
                    return TradeResult(
                        success=False,
                        signatures=[],
                        error="Multiple SWQOS transactions require durable_nonce to be set",
                    )

                submit_results: List[str] = []
                errors: List[str] = []
                tasks = []
                for cfg in swqos_configs:
                    sender_cfg = SenderSwqosConfig(
                        type=cfg.type,
                        region=cfg.region,
                        custom_url=cfg.custom_url,
                        api_key=cfg.api_key,
                        mev_protection=cfg.mev_protection,
                        transport=cfg.transport,
                        astralane_transport=cfg.astralane_transport,
                        swqos_only=cfg.swqos_only,
                    )
                    client = SwqosClientFactory.create_client(sender_cfg, self.config.rpc_url)
                    tip_recipient_for_client: Optional[Pubkey] = None
                    if with_tip and getattr(cfg.type, "value", cfg.type) != "Default":
                        tip_account = client.get_tip_account()
                        if tip_account:
                            tip_recipient_for_client = Pubkey.from_string(tip_account)
                    tx_for_client = self._build_transaction(
                        self._build_wired_instructions(
                            instructions,
                            trade_type,
                            gas_fee_strategy,
                            with_tip,
                            durable_nonce,
                            dex_type,
                            tip_recipient_for_client,
                        ),
                        effective_blockhash,
                        address_lookup_table_account,
                    )
                    tasks.append(client.send_transaction(trade_type, bytes(tx_for_client), wait_confirmed))

                if not wait_confirmed and not wait_for_all_submits:
                    for pending in asyncio.as_completed(tasks):
                        try:
                            signature = await pending
                            submit_results.append(str(signature))
                            break
                        except Exception as exc:
                            errors.append(str(exc))
                else:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for item in results:
                        if isinstance(item, Exception):
                            errors.append(str(item))
                        else:
                            submit_results.append(str(item))

                if not submit_results:
                    return TradeResult(
                        success=False,
                        signatures=[],
                        error="; ".join(errors) or "All SWQOS submissions failed",
                    )

                if wait_confirmed:
                    from .trading.executor import poll_for_confirmation_error

                    confirmed = False
                    last_confirm_error: Optional[str] = None
                    for signature in submit_results:
                        ok, confirm_error = await poll_for_confirmation_error(self.config.rpc_url, signature)
                        if ok:
                            confirmed = True
                            break
                        last_confirm_error = confirm_error
                    if not confirmed:
                        return TradeResult(
                            success=False,
                            signatures=submit_results,
                            error=last_confirm_error or "transaction confirmation failed",
                        )

                return TradeResult(
                    success=True,
                    signatures=submit_results,
                )

            sig = await self.client.send_raw_transaction(bytes(transaction))
            signature = sig.value

            if wait_confirmed:
                from .trading.executor import poll_for_confirmation_error

                ok, confirm_error = await poll_for_confirmation_error(self.config.rpc_url, str(signature))
                if not ok:
                    return TradeResult(
                        success=False,
                        signatures=[str(signature)],
                        error=confirm_error or "transaction confirmation failed",
                    )

            return TradeResult(
                success=True,
                signatures=[str(signature)],
            )
        except Exception as e:
            return TradeResult(
                success=False,
                signatures=[],
                error=str(e),
            )


# ============== Helper Functions ==============


def create_flat_gas_fee_strategy() -> _FlatGasFeeStrategy:
    """Create a new gas fee strategy with defaults"""
    return _FlatGasFeeStrategy()


def create_trade_config(
    rpc_url: str,
    swqos_configs: Optional[List[SwqosConfig]] = None,
    **options: Any,
) -> TradeConfig:
    """Create a new trade config"""
    return TradeConfig(
        rpc_url=rpc_url,
        swqos_configs=swqos_configs or [],
        **options,
    )


# ============== Hot Path Exports ==============

from .hotpath import (
    HotPathConfig,
    HotPathState,
    HotPathExecutor,
    HotPathMetrics,
    TradingContext,
    PrefetchedData,
    AccountState,
    PoolState,
    ExecuteOptions,
    ExecuteResult,
    TransactionBuilder,
    HotPathError,
    StaleBlockhashError,
    MissingAccountError,
    ContextExpiredError,
    create_hot_path_executor,
)

from .common.types import (
    GasFeeStrategy,
    GasFeeStrategyType,
    GasFeeStrategyValue,
    TradeType,
    SwqosType,
    BondingCurveAccount,
    NonceCache,
)
from .common.gas_fee_strategy import create_gas_fee_strategy
from .cache import LRUCache, TTLCache, ShardedCache
from .pool import WorkerPool, RateLimiter, MultiRateLimiter
from .calc import (
    ceil_div,
    calculate_with_slippage_buy,
    calculate_with_slippage_sell,
    get_buy_token_amount_from_sol_amount,
    get_sell_sol_amount_from_token_amount,
    raydium_amm_v4_get_amount_out,
    lamports_to_sol,
    sol_to_lamports,
)
from .calc import (
    buy_base_input_internal as _calc_buy_base_input_internal,
    sell_base_input_internal as _calc_sell_base_input_internal,
)
from .seed import find_program_address, get_bonding_curve_pda, get_associated_token_address
from .spl_token import TokenAccount, transfer_instruction, close_account_instruction
from .instruction import PumpFunInstructionBuilder
from .trading import (
    TradeExecutor,
    TradeConfig as TradeExecutorConfig,
    ExecuteOptions as TradeExecutorOptions,
    default_execute_options,
)


@dataclass
class BuildParams:
    """Generic instruction build parameters used by compatibility tests."""

    payer: bytes
    input_mint: bytes
    output_mint: bytes
    input_amount: int
    slippage_bps: int
    protocol_params: Any


def compute_fee(amount: int, fee_basis_points: int, denominator: int = 10_000) -> int:
    """Calculate a fee with ceiling division."""

    return ceil_div(amount * fee_basis_points, denominator)


def buy_base_input_internal(
    base: int,
    base_reserve: int,
    quote_reserve: int,
    slippage_basis_points: int,
    has_coin_creator: bool = False,
):
    """Compatibility wrapper using the public argument order from tests/docs."""

    return _calc_buy_base_input_internal(
        base,
        slippage_basis_points,
        base_reserve,
        quote_reserve,
        has_coin_creator,
    )


def sell_base_input_internal(
    base: int,
    base_reserve: int,
    quote_reserve: int,
    slippage_basis_points: int,
    has_coin_creator: bool = False,
):
    """Compatibility wrapper using the public argument order from tests/docs."""

    return _calc_sell_base_input_internal(
        base,
        slippage_basis_points,
        base_reserve,
        quote_reserve,
        has_coin_creator,
    )

__all__ = [
    # Enums
    "DexType",
    "TradeTokenType",
    "AccountPolicy",
    "BuyAmount",
    "SellAmount",
    "TradeType",
    "SwqosRegion",
    "SwqosType",
    "SwqosTransport",
    "AstralaneTransport",
    "GasFeeStrategyType",
    "GasFeeStrategyValue",
    # Data Classes
    "SwqosConfig",
    "GasFeeStrategy",
    "DurableNonceInfo",
    "NonceCache",
    "BondingCurveAccount",
    "TradeResult",
    # Protocol Params
    "PumpFunParams",
    "PumpSwapFeeBasisPoints",
    "PumpSwapParams",
    "BonkParams",
    "RaydiumCpmmParams",
    "RaydiumAmmV4Params",
    "MeteoraDammV2Params",
    # Trade Params
    "TradeBuyParams",
    "TradeSellParams",
    "SimpleBuyParams",
    "SimpleSellParams",
    # Client
    "TradeConfig",
    "TradeConfigBuilder",
    "TradingClient",
    # Helper Functions
    "create_gas_fee_strategy",
    "create_trade_config",
    "recommended_sender_thread_core_indices",
    "simple_buy_params_to_trade_buy_params",
    "simple_sell_params_to_trade_sell_params",
    "compute_fee",
    "ceil_div",
    "calculate_with_slippage_buy",
    "calculate_with_slippage_sell",
    "get_buy_token_amount_from_sol_amount",
    "get_sell_sol_amount_from_token_amount",
    "buy_base_input_internal",
    "sell_base_input_internal",
    "raydium_amm_v4_get_amount_out",
    "lamports_to_sol",
    "sol_to_lamports",
    "LRUCache",
    "TTLCache",
    "ShardedCache",
    "WorkerPool",
    "RateLimiter",
    "MultiRateLimiter",
    "find_program_address",
    "get_bonding_curve_pda",
    "get_associated_token_address",
    "TokenAccount",
    "transfer_instruction",
    "close_account_instruction",
    "PumpFunInstructionBuilder",
    "BuildParams",
    "TradeExecutor",
    "TradeExecutorConfig",
    "TradeExecutorOptions",
    "default_execute_options",
    # Constants
    "SYSTEM_PROGRAM",
    "TOKEN_PROGRAM",
    "TOKEN_PROGRAM_2022",
    "SOL_TOKEN_ACCOUNT",
    "WSOL_TOKEN_ACCOUNT",
    "USD1_TOKEN_ACCOUNT",
    "USDC_TOKEN_ACCOUNT",
    "ASSOCIATED_TOKEN_PROGRAM",
    "RENT",
    "PUMPFUN_PROGRAM",
    "PUMPSWAP_PROGRAM",
    "BONK_PROGRAM",
    "RAYDIUM_CPMM_PROGRAM",
    "RAYDIUM_AMM_V4_PROGRAM",
    "FEE_RECIPIENT",
    "DEFAULT_SLIPPAGE",
    "DEFAULT_COMPUTE_UNITS",
    "DEFAULT_PRIORITY_FEE",
    "DEFAULT_TIP_LAMPORTS",
    # Hot Path
    "HotPathConfig",
    "HotPathState",
    "HotPathExecutor",
    "HotPathMetrics",
    "TradingContext",
    "PrefetchedData",
    "AccountState",
    "PoolState",
    "ExecuteOptions",
    "ExecuteResult",
    "TransactionBuilder",
    "HotPathError",
    "StaleBlockhashError",
    "MissingAccountError",
    "ContextExpiredError",
    "create_hot_path_executor",
]
