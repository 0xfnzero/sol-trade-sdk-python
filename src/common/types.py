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
    SOLAMI = "Solami"
    LUNAR_LANDER = "LunarLander"
    GLAIVE = "Glaive"
    DEFAULT = "Default"


class SwqosTransport(Enum):
    """SWQOS transport mode."""

    HTTP = "Http"
    GRPC = "Grpc"
    QUIC = "Quic"


class SwqosRegion(Enum):
    """SWQOS service regions"""
    NEW_YORK = "NewYork"
    FRANKFURT = "Frankfurt"
    AMSTERDAM = "Amsterdam"
    DUBLIN = "Dublin"
    SLC = "SLC"
    TOKYO = "Tokyo"
    SINGAPORE = "Singapore"
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
INITIAL_REAL_TOKEN_RESERVES = 793100000000000
TOKEN_TOTAL_SUPPLY = 1000000000000000
FEE_BASIS_POINTS = 95  # Pinned fallback, not current fee discovery.
CREATOR_FEE = 30


# One native implementation for every public import path.
from .bonding_curve import BondingCurveAccount


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
