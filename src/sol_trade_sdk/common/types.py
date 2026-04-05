"""
Core types for Sol Trade SDK
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, Dict, Tuple
from threading import Lock
import time


class GasFeeStrategyType(Enum):
    """Type of gas fee strategy"""
    NORMAL = "Normal"
    LOW_TIP_HIGH_CU_PRICE = "LowTipHighCuPrice"
    HIGH_TIP_LOW_CU_PRICE = "HighTipLowCuPrice"


class TradeType(Enum):
    """Type of trade operation"""
    CREATE = "Create"
    CREATE_AND_BUY = "CreateAndBuy"
    BUY = "Buy"
    SELL = "Sell"


class SwqosType(Enum):
    """SWQOS service provider types"""
    JITO = "Jito"
    NEXT_BLOCK = "NextBlock"
    ZERO_SLOT = "ZeroSlot"
    TEMPORAL = "Temporal"
    BLOXROUTE = "Bloxroute"
    NODE1 = "Node1"
    FLASH_BLOCK = "FlashBlock"
    BLOCK_RAZOR = "BlockRazor"
    ASTRALANE = "Astralane"
    STELLIUM = "Stellium"
    LIGHTSPEED = "Lightspeed"
    SOYAS = "Soyas"
    SPEEDLANDING = "Speedlanding"
    HELIUS = "Helius"
    DEFAULT = "Default"


class SwqosRegion(Enum):
    """SWQOS service regions"""
    NEW_YORK = "NewYork"
    FRANKFURT = "Frankfurt"
    AMSTERDAM = "Amsterdam"
    SLC = "SLC"
    TOKYO = "Tokyo"
    LONDON = "London"
    LOS_ANGELES = "LosAngeles"
    DEFAULT = "Default"


@dataclass
class GasFeeStrategyValue:
    """Gas fee configuration values"""
    cu_limit: int
    cu_price: int
    tip: float


@dataclass
class StrategyKey:
    """Key for gas fee strategy map"""
    swqos_type: SwqosType
    trade_type: TradeType
    strategy_type: GasFeeStrategyType

    def __hash__(self):
        return hash((self.swqos_type, self.trade_type, self.strategy_type))


@dataclass
class StrategyResult:
    """Strategy search result"""
    swqos_type: SwqosType
    strategy_type: GasFeeStrategyType
    value: GasFeeStrategyValue


class GasFeeStrategy:
    """
    Manages gas fee configurations for different SWQOS types.
    Thread-safe implementation using locks.
    """

    def __init__(self):
        self._strategies: Dict[StrategyKey, GasFeeStrategyValue] = {}
        self._lock = Lock()

    def set_global_fee_strategy(
        self,
        buy_cu_limit: int,
        sell_cu_limit: int,
        buy_cu_price: int,
        sell_cu_price: int,
        buy_tip: float,
        sell_tip: float,
    ) -> None:
        """Set global fee strategy for all SWQOS types"""
        with self._lock:
            for swqos_type in SwqosType:
                if swqos_type == SwqosType.DEFAULT:
                    continue
                self._set_internal(
                    swqos_type, TradeType.BUY, GasFeeStrategyType.NORMAL,
                    buy_cu_limit, buy_cu_price, buy_tip
                )
                self._set_internal(
                    swqos_type, TradeType.SELL, GasFeeStrategyType.NORMAL,
                    sell_cu_limit, sell_cu_price, sell_tip
                )
            # Default (RPC) has no tip
            self._set_internal(
                SwqosType.DEFAULT, TradeType.BUY, GasFeeStrategyType.NORMAL,
                buy_cu_limit, buy_cu_price, 0
            )
            self._set_internal(
                SwqosType.DEFAULT, TradeType.SELL, GasFeeStrategyType.NORMAL,
                sell_cu_limit, sell_cu_price, 0
            )

    def set_high_low_fee_strategies(
        self,
        swqos_types: list,
        trade_type: TradeType,
        cu_limit: int,
        low_cu_price: int,
        high_cu_price: int,
        low_tip: float,
        high_tip: float,
    ) -> None:
        """Set high-low fee strategies for multiple SWQOS types"""
        with self._lock:
            for swqos_type in swqos_types:
                self._delete_internal(swqos_type, trade_type, GasFeeStrategyType.NORMAL)
                self._set_internal(
                    swqos_type, trade_type, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE,
                    cu_limit, high_cu_price, low_tip
                )
                self._set_internal(
                    swqos_type, trade_type, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE,
                    cu_limit, low_cu_price, high_tip
                )

    def set(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
        cu_limit: int,
        cu_price: int,
        tip: float,
    ) -> None:
        """Set a specific gas fee strategy"""
        with self._lock:
            self._set_internal(swqos_type, trade_type, strategy_type, cu_limit, cu_price, tip)

    def _set_internal(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
        cu_limit: int,
        cu_price: int,
        tip: float,
    ) -> None:
        """Internal set without lock (must be called with lock held)"""
        key = StrategyKey(swqos_type, trade_type, strategy_type)

        # Remove conflicting strategies
        if strategy_type == GasFeeStrategyType.NORMAL:
            self._delete_internal(swqos_type, trade_type, GasFeeStrategyType.LOW_TIP_HIGH_CU_PRICE)
            self._delete_internal(swqos_type, trade_type, GasFeeStrategyType.HIGH_TIP_LOW_CU_PRICE)
        else:
            self._delete_internal(swqos_type, trade_type, GasFeeStrategyType.NORMAL)

        self._strategies[key] = GasFeeStrategyValue(cu_limit, cu_price, tip)

    def get(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
    ) -> Optional[GasFeeStrategyValue]:
        """Get a specific gas fee strategy"""
        with self._lock:
            key = StrategyKey(swqos_type, trade_type, strategy_type)
            return self._strategies.get(key)

    def delete(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
    ) -> None:
        """Delete a specific gas fee strategy"""
        with self._lock:
            self._delete_internal(swqos_type, trade_type, strategy_type)

    def _delete_internal(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
    ) -> None:
        """Internal delete without lock"""
        key = StrategyKey(swqos_type, trade_type, strategy_type)
        self._strategies.pop(key, None)

    def delete_all(self, swqos_type: SwqosType, trade_type: TradeType) -> None:
        """Delete all strategies for a SWQOS type and trade type"""
        with self._lock:
            for strategy_type in GasFeeStrategyType:
                self._delete_internal(swqos_type, trade_type, strategy_type)

    def get_strategies(self, trade_type: TradeType) -> list:
        """Get all strategies for a trade type"""
        with self._lock:
            results = []
            for key, value in self._strategies.items():
                if key.trade_type == trade_type:
                    results.append(StrategyResult(
                        swqos_type=key.swqos_type,
                        strategy_type=key.strategy_type,
                        value=value
                    ))
            return results

    def update_buy_tip(self, buy_tip: float) -> None:
        """Update buy tip for all strategies"""
        with self._lock:
            for key, value in self._strategies.items():
                if key.trade_type == TradeType.BUY:
                    value.tip = buy_tip

    def update_sell_tip(self, sell_tip: float) -> None:
        """Update sell tip for all strategies"""
        with self._lock:
            for key, value in self._strategies.items():
                if key.trade_type == TradeType.SELL:
                    value.tip = sell_tip

    def clear(self) -> None:
        """Clear all strategies"""
        with self._lock:
            self._strategies.clear()


# ===== Bonding Curve =====

# Constants for bonding curve calculations
INITIAL_VIRTUAL_TOKEN_RESERVES = 1073000000000000
INITIAL_VIRTUAL_SOL_RESERVES = 30000000000
INITIAL_REAL_TOKEN_RESERVES = 793000000000000
TOKEN_TOTAL_SUPPLY = 1000000000000000
FEE_BASIS_POINTS = 100  # 1%
CREATOR_FEE = 50  # 0.5%


@dataclass
class BondingCurveAccount:
    """
    Represents the bonding curve state for PumpFun tokens.
    Implements constant product formula for token pricing.
    """
    discriminator: int = 0
    account: bytes = field(default_factory=lambda: bytes(32))
    virtual_token_reserves: int = INITIAL_VIRTUAL_TOKEN_RESERVES
    virtual_sol_reserves: int = INITIAL_VIRTUAL_SOL_RESERVES
    real_token_reserves: int = INITIAL_REAL_TOKEN_RESERVES
    real_sol_reserves: int = 0
    token_total_supply: int = TOKEN_TOTAL_SUPPLY
    complete: bool = False
    creator: bytes = field(default_factory=lambda: bytes(32))
    is_mayhem_mode: bool = False
    is_cashback_coin: bool = False

    def get_buy_price(self, amount: int) -> int:
        """
        Calculate the amount of tokens received for a given SOL amount.
        Uses constant product formula: tokens = virtual_tokens - (sol_reserves * virtual_tokens) / (sol_reserves + amount)
        """
        if self.complete or amount == 0:
            return 0

        # n = virtual_sol_reserves * virtual_token_reserves
        n = self.virtual_sol_reserves * self.virtual_token_reserves
        # i = virtual_sol_reserves + amount
        i = self.virtual_sol_reserves + amount
        # r = n / i + 1
        r = n // i + 1
        # s = virtual_token_reserves - r
        s = self.virtual_token_reserves - r

        if s < self.real_token_reserves:
            return s
        return self.real_token_reserves

    def get_sell_price(self, amount: int, fee_basis_points: int = FEE_BASIS_POINTS) -> int:
        """
        Calculate the amount of SOL received for selling tokens.
        Applies fee deduction from the output.
        """
        if self.complete or amount == 0:
            return 0

        # n = (amount * virtual_sol_reserves) / (virtual_token_reserves + amount)
        n = (amount * self.virtual_sol_reserves) // (self.virtual_token_reserves + amount)
        # a = (n * fee_basis_points) / 10000
        a = (n * fee_basis_points) // 10000

        return n - a

    def get_market_cap_sol(self) -> int:
        """Calculate the current market cap in SOL"""
        if self.virtual_token_reserves == 0:
            return 0
        return (self.token_total_supply * self.virtual_sol_reserves) // self.virtual_token_reserves

    def get_token_price(self) -> float:
        """Calculate the token price in SOL"""
        if self.virtual_token_reserves == 0:
            return 0.0
        v_sol = self.virtual_sol_reserves / 100_000_000.0
        v_tokens = self.virtual_token_reserves / 100_000.0
        return v_sol / v_tokens


# ===== Nonce Cache =====

@dataclass
class DurableNonceInfo:
    """Durable nonce information for transaction sequencing"""
    nonce_account: bytes
    authority: bytes
    nonce_hash: bytes
    recent_blockhash: bytes


class NonceCache:
    """Thread-safe cache for nonce information"""

    def __init__(self):
        self._nonces: Dict[bytes, DurableNonceInfo] = {}
        self._lock = Lock()

    def set(self, pubkey: bytes, info: DurableNonceInfo) -> None:
        """Set a nonce in the cache"""
        with self._lock:
            self._nonces[pubkey] = info

    def get(self, pubkey: bytes) -> Optional[DurableNonceInfo]:
        """Get a nonce from the cache"""
        with self._lock:
            return self._nonces.get(pubkey)

    def delete(self, pubkey: bytes) -> None:
        """Delete a nonce from the cache"""
        with self._lock:
            self._nonces.pop(pubkey, None)


# ===== Rent =====

_spl_token_rent = 0
_spl_token_2022_rent = 0
_DEFAULT_TOKEN_RENT = 2_039_280  # ~0.00203928 SOL


def get_token_account_rent(is_token_2022: bool = False) -> int:
    """Get the rent for a token account"""
    global _spl_token_rent, _spl_token_2022_rent
    if is_token_2022:
        if _spl_token_2022_rent != 0:
            return _spl_token_2022_rent
        return _DEFAULT_TOKEN_RENT
    if _spl_token_rent != 0:
        return _spl_token_rent
    return _DEFAULT_TOKEN_RENT


def set_token_account_rent(is_token_2022: bool, rent: int) -> None:
    """Set the rent for token accounts"""
    global _spl_token_rent, _spl_token_2022_rent
    if is_token_2022:
        _spl_token_2022_rent = rent
    else:
        _spl_token_rent = rent


# ===== Clock =====

_global_clock = 0
_clock_lock = Lock()


def now_microseconds() -> int:
    """Get current time in microseconds"""
    with _clock_lock:
        if _global_clock == 0:
            return int(time.time() * 1_000_000)
        return _global_clock


def set_clock_time(t: int) -> None:
    """Set the global clock time (for testing)"""
    global _global_clock
    with _clock_lock:
        _global_clock = t
