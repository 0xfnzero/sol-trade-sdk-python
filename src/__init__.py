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
from solders.message import Message
from solders.instruction import Instruction, AccountMeta
from solders.hash import Hash as Blockhash
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


# ============== Data Classes ==============


@dataclass
class SwqosConfig:
    """SWQOS service configuration"""

    type: SwqosType
    region: SwqosRegion
    api_key: str
    custom_url: Optional[str] = None
    mev_protection: Optional[bool] = None
    transport: Optional[SwqosTransport] = None
    astralane_transport: Optional[AstralaneTransport] = None
    swqos_only: Optional[bool] = None


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
    use_v2_ix: bool = False
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

    def with_quote_mint(self, quote_mint: Pubkey, use_v2_ix: bool = True) -> "PumpFunParams":
        """Set PumpFun V2 quote mint and enable V2 instructions by default."""
        self.quote_mint = quote_mint
        self.use_v2_ix = use_v2_ix
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
    # MEV protection: when enabled, BlockRazor uses sandwichMitigation mode,
    # Astralane uses port 9000 (MEV-protected QUIC endpoint)
    mev_protection: bool = False
    use_seed_optimize: bool = True
    create_wsol_ata_on_startup: bool = False
    use_pumpfun_v2: bool = False
    swqos_cores_from_end: bool = True
    max_swqos_submit_concurrency: Optional[int] = None

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
        self._create_wsol_ata_on_startup: bool = False
        self._use_pumpfun_v2: bool = False
        self._swqos_cores_from_end: bool = True
        self._max_swqos_submit_concurrency: Optional[int] = None

    def swqos_configs(self, configs: List[SwqosConfig]) -> "TradeConfigBuilder":
        """Set SWQOS provider configurations."""
        self._swqos_configs = configs
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

    def use_pumpfun_v2(self, enabled: bool) -> "TradeConfigBuilder":
        self._use_pumpfun_v2 = enabled
        return self

    def swqos_cores_from_end(self, enabled: bool) -> "TradeConfigBuilder":
        self._swqos_cores_from_end = enabled
        return self

    def max_swqos_submit_concurrency(self, limit: Optional[int]) -> "TradeConfigBuilder":
        self._max_swqos_submit_concurrency = limit
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
            use_pumpfun_v2=self._use_pumpfun_v2,
            swqos_cores_from_end=self._swqos_cores_from_end,
            max_swqos_submit_concurrency=self._max_swqos_submit_concurrency,
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
    count = min(swqos_count, cores)
    if from_end:
        return list(range(cores - count, cores))
    return list(range(count))


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

        protocol_params = params.extension_params
        if (
            params.dex_type == DexType.PUMPFUN
            and isinstance(protocol_params, PumpFunParams)
            and self.config.use_pumpfun_v2
        ):
            protocol_params = replace(protocol_params, use_v2_ix=True)

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
                use_pumpfun_v2=self.config.use_pumpfun_v2,
            )
        instructions = await builder.build_buy_instructions(**buy_kwargs)

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

        protocol_params = params.extension_params
        if (
            params.dex_type == DexType.PUMPFUN
            and isinstance(protocol_params, PumpFunParams)
            and self.config.use_pumpfun_v2
        ):
            protocol_params = replace(protocol_params, use_v2_ix=True)

        builder = self._create_instruction_builder(params.dex_type)
        sell_kwargs = dict(
            payer=self.payer.pubkey(),
            input_mint=params.mint,
            output_mint=self._get_output_mint(params.output_token_type),
            input_amount=params.input_token_amount,
            slippage_basis_points=params.slippage_basis_points or DEFAULT_SLIPPAGE,
            protocol_params=protocol_params,
            create_output_ata=params.create_output_token_ata,
            close_input_ata=params.close_mint_token_ata,
        )
        if params.dex_type == DexType.PUMPFUN:
            sell_kwargs.update(
                fixed_output_amount=params.fixed_output_token_amount,
                use_pumpfun_v2=self.config.use_pumpfun_v2,
            )
        instructions = await builder.build_sell_instructions(**sell_kwargs)

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
        result = await self._execute_transaction(instructions, None, True)
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
    DurableNonceInfo,
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
from .trading import TradeExecutor, TradeConfig, ExecuteOptions, default_execute_options


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
    "TradeConfigBuilder",
    "TradingClient",
    # Helper Functions
    "create_gas_fee_strategy",
    "create_trade_config",
    "recommended_sender_thread_core_indices",
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
    "ExecuteOptions",
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
