"""
Sol Trade SDK - Python SDK for Solana DEX trading

A comprehensive SDK for seamless Solana DEX trading with support for
PumpFun, PumpSwap, Bonk, Raydium CPMM, Raydium AMM V4, and Meteora DAMM V2.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
import asyncio
import time

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solders.signature import Signature
from solders.transaction import Transaction
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment, Confirmed
from solana.transaction import Blockhash

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


class TradeType(Enum):
    """Trade operation type"""

    BUY = "Buy"
    SELL = "Sell"


class SwqosRegion(Enum):
    """SWQOS service regions"""

    FRANKFURT = "Frankfurt"
    NEW_YORK = "NewYork"
    AMSTERDAM = "Amsterdam"
    TOKYO = "Tokyo"
    SINGAPORE = "Singapore"


class SwqosType(Enum):
    """SWQOS service types"""

    DEFAULT = "Default"
    JITO = "Jito"
    BLOXROUTE = "Bloxroute"
    ZEROSLOT = "ZeroSlot"
    TEMPORAL = "Temporal"
    FLASHBLOCK = "FlashBlock"
    BLOCKRAZOR = "BlockRazor"
    NODE1 = "Node1"
    ASTRALANE = "Astralane"
    NEXTBLOCK = "NextBlock"
    HELIUS = "Helius"


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


# ============== Data Classes ==============


@dataclass
class SwqosConfig:
    """SWQOS service configuration"""

    type: SwqosType
    region: SwqosRegion
    api_key: str
    custom_url: Optional[str] = None


@dataclass
class GasFeeStrategy:
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


# ============== Protocol Params ==============


@dataclass
class PumpFunParams:
    """PumpFun protocol parameters"""

    bonding_curve: BondingCurveAccount
    associated_bonding_curve: Pubkey
    creator_vault: Pubkey
    token_program: Pubkey
    close_token_account_when_sell: Optional[bool] = None

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
    is_mayhem_mode: bool
    is_cashback_coin: bool


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
    wait_tx_confirmed: bool = True
    create_input_token_ata: bool = True
    close_input_token_ata: bool = False
    create_mint_ata: bool = True
    durable_nonce: Optional[DurableNonceInfo] = None
    fixed_output_token_amount: Optional[int] = None
    gas_fee_strategy: Optional[GasFeeStrategy] = None
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
    wait_tx_confirmed: bool = True
    create_output_token_ata: bool = False
    close_output_token_ata: bool = False
    close_mint_token_ata: bool = False
    durable_nonce: Optional[DurableNonceInfo] = None
    fixed_output_token_amount: Optional[int] = None
    gas_fee_strategy: Optional[GasFeeStrategy] = None
    simulate: bool = False
    grpc_recv_us: Optional[int] = None


# ============== Main Client ==============


@dataclass
class TradeConfig:
    """Trading configuration"""

    rpc_url: str
    swqos_configs: List[SwqosConfig] = field(default_factory=list)
    commitment: Commitment = Confirmed
    log_enabled: bool = True
    check_min_tip: bool = False


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

        # Build instructions
        builder = self._create_instruction_builder(params.dex_type)
        instructions = await builder.build_buy_instructions(
            payer=self.payer.pubkey(),
            input_mint=self._get_input_mint(params.input_token_type),
            output_mint=params.mint,
            input_amount=params.input_token_amount,
            slippage_basis_points=params.slippage_basis_points or DEFAULT_SLIPPAGE,
            protocol_params=params.extension_params,
            create_output_ata=params.create_mint_ata,
            close_input_ata=params.close_input_token_ata,
        )

        # Process middlewares
        for middleware in self.middlewares:
            instructions = await middleware.process(instructions)

        # Execute transaction
        return await self._execute_transaction(
            instructions, params.recent_blockhash, params.wait_tx_confirmed
        )

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

        builder = self._create_instruction_builder(params.dex_type)
        instructions = await builder.build_sell_instructions(
            payer=self.payer.pubkey(),
            input_mint=params.mint,
            output_mint=self._get_output_mint(params.output_token_type),
            input_amount=params.input_token_amount,
            slippage_basis_points=params.slippage_basis_points or DEFAULT_SLIPPAGE,
            protocol_params=params.extension_params,
            create_output_ata=params.create_output_token_ata,
            close_input_ata=params.close_mint_token_ata,
        )

        for middleware in self.middlewares:
            instructions = await middleware.process(instructions)

        return await self._execute_transaction(
            instructions, params.recent_blockhash, params.wait_tx_confirmed
        )

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
        # Implementation requires WSOL manager
        raise NotImplementedError("wrap_sol_to_wsol not implemented")

    async def close_wsol(self) -> str:
        """Close WSOL account and unwrap to SOL"""
        raise NotImplementedError("close_wsol not implemented")

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
    ) -> TradeResult:
        """Execute transaction with instructions"""
        try:
            if blockhash is None:
                bh = await self.get_latest_blockhash()
                blockhash = str(bh.blockhash)

            message = Message.new_with_blockhash(
                instructions, self.payer.pubkey(), Pubkey.from_string(blockhash)
            )

            transaction = Transaction.new_unsigned(message)
            transaction.sign([self.payer], Pubkey.from_string(blockhash))

            sig = await self.client.send_raw_transaction(bytes(transaction))
            signature = sig.value

            if wait_confirmed:
                await self.client.confirm_transaction(signature)

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


def create_gas_fee_strategy() -> GasFeeStrategy:
    """Create a new gas fee strategy with defaults"""
    return GasFeeStrategy()


def create_trade_config(
    rpc_url: str, swqos_configs: Optional[List[SwqosConfig]] = None
) -> TradeConfig:
    """Create a new trade config"""
    return TradeConfig(
        rpc_url=rpc_url,
        swqos_configs=swqos_configs or [],
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

__all__ = [
    # Enums
    "DexType",
    "TradeTokenType",
    "TradeType",
    "SwqosRegion",
    "SwqosType",
    # Data Classes
    "SwqosConfig",
    "GasFeeStrategy",
    "DurableNonceInfo",
    "BondingCurveAccount",
    "TradeResult",
    # Protocol Params
    "PumpFunParams",
    "PumpSwapParams",
    "BonkParams",
    "RaydiumCpmmParams",
    "RaydiumAmmV4Params",
    "MeteoraDammV2Params",
    # Trade Params
    "TradeBuyParams",
    "TradeSellParams",
    # Client
    "TradeConfig",
    "TradingClient",
    # Helper Functions
    "create_gas_fee_strategy",
    "create_trade_config",
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
