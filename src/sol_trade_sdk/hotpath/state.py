"""
Hot Path State Management for Sol Trade SDK

This module provides state management optimized for hot trading paths.
NO RPC calls are made during trading execution - all data is prefetched.

Key principle: Prepare everything before the trade, execute with zero I/O latency.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any, Tuple
from collections import defaultdict
import threading
from concurrent.futures import ThreadPoolExecutor

try:
    from solders.hash import Hash
    from solders.pubkey import Pubkey
    from solders.signature import Signature
    from solders.transaction import VersionedTransaction
    HAS_SOLDERS = True
except ImportError:
    HAS_SOLDERS = False


@dataclass
class HotPathConfig:
    """Configuration for hot path state management"""
    blockhash_refresh_interval: float = 2.0  # seconds
    cache_ttl: float = 5.0  # seconds
    enable_prefetch: bool = True
    max_retries: int = 3
    prefetch_timeout: float = 5.0


@dataclass
class PrefetchedData:
    """Container for prefetched blockchain data"""
    blockhash: Optional[str] = None
    last_valid_height: int = 0
    slot: int = 0
    fetched_at: float = 0.0  # timestamp

    def is_fresh(self, ttl: float) -> bool:
        """Check if data is still fresh"""
        if self.fetched_at == 0.0:
            return False
        return (time.time() - self.fetched_at) <= ttl

    def age(self) -> float:
        """Get age of data in seconds"""
        return time.time() - self.fetched_at


@dataclass
class AccountState:
    """Cached account state"""
    pubkey: str
    data: bytes
    lamports: int
    owner: str
    executable: bool
    rent_epoch: int
    slot: int
    fetched_at: float = field(default_factory=time.time)

    def is_fresh(self, ttl: float) -> bool:
        return (time.time() - self.fetched_at) <= ttl


@dataclass
class PoolState:
    """Cached DEX pool state"""
    pool_address: str
    pool_type: str  # 'pumpfun', 'pumpswap', 'raydium', 'meteora'
    mint_a: str
    mint_b: str
    vault_a: str
    vault_b: str
    reserve_a: int
    reserve_b: int
    fee_rate: float
    fetched_at: float = field(default_factory=time.time)
    raw_data: bytes = b''

    def is_fresh(self, ttl: float) -> bool:
        return (time.time() - self.fetched_at) <= ttl


class HotPathState:
    """
    Manages prefetched state for hot path execution.
    
    Key design:
    - All RPC calls happen in background prefetch loops
    - Hot path methods (get_blockhash, get_account) never make RPC calls
    - Thread-safe for concurrent access
    """
    
    def __init__(
        self,
        rpc_client: Any,  # AsyncRPCClient
        config: Optional[HotPathConfig] = None,
    ):
        self.config = config or HotPathConfig()
        self.rpc_client = rpc_client
        
        # Prefetched data storage
        self._current_data: PrefetchedData = PrefetchedData()
        self._accounts: Dict[str, AccountState] = {}
        self._pools: Dict[str, PoolState] = {}
        
        # Thread safety
        self._lock = threading.RLock()
        self._data_lock = threading.Lock()
        
        # Background task control
        self._prefetch_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks
        self._on_blockhash_update: Optional[Callable] = None
        
        # Metrics
        self._metrics = {
            'prefetch_count': 0,
            'prefetch_errors': 0,
            'last_prefetch_time': 0.0,
        }
    
    async def start(self) -> None:
        """Start background prefetching"""
        if not self.config.enable_prefetch:
            return
        
        # Initial synchronous prefetch
        await self._prefetch_blockhash()
        
        # Start background loop
        self._running = True
        self._prefetch_task = asyncio.create_task(self._prefetch_loop())
    
    async def stop(self) -> None:
        """Stop background prefetching"""
        self._running = False
        if self._prefetch_task:
            self._prefetch_task.cancel()
            try:
                await self._prefetch_task
            except asyncio.CancelledError:
                pass
    
    async def _prefetch_loop(self) -> None:
        """Background loop to keep data fresh"""
        while self._running:
            try:
                await asyncio.sleep(self.config.blockhash_refresh_interval)
                await self._prefetch_blockhash()
            except asyncio.CancelledError:
                break
            except Exception:
                with self._lock:
                    self._metrics['prefetch_errors'] += 1
    
    async def _prefetch_blockhash(self) -> None:
        """
        Prefetch latest blockhash - RPC call happens here (background only)
        """
        try:
            result = await asyncio.wait_for(
                self.rpc_client.get_latest_blockhash(),
                timeout=self.config.prefetch_timeout
            )
            
            with self._data_lock:
                self._current_data = PrefetchedData(
                    blockhash=result['blockhash'],
                    last_valid_height=result['last_valid_block_height'],
                    slot=result.get('slot', 0),
                    fetched_at=time.time(),
                )
            
            with self._lock:
                self._metrics['prefetch_count'] += 1
                self._metrics['last_prefetch_time'] = time.time()
            
            if self._on_blockhash_update:
                self._on_blockhash_update(
                    self._current_data.blockhash,
                    self._current_data.last_valid_height
                )
                
        except Exception as e:
            with self._lock:
                self._metrics['prefetch_errors'] += 1
            raise
    
    def get_blockhash(self) -> Tuple[Optional[str], int, bool]:
        """
        Get current cached blockhash - NO RPC CALL
        
        Returns:
            Tuple of (blockhash, last_valid_height, is_valid)
        """
        with self._data_lock:
            if not self._current_data.is_fresh(self.config.cache_ttl):
                return None, 0, False
            return (
                self._current_data.blockhash,
                self._current_data.last_valid_height,
                True
            )
    
    def is_data_fresh(self) -> bool:
        """Check if prefetched data is still valid"""
        with self._data_lock:
            return self._current_data.is_fresh(self.config.cache_ttl)
    
    def get_prefetched_data(self) -> PrefetchedData:
        """Get all prefetched data - NO RPC CALL"""
        with self._data_lock:
            return self._current_data
    
    def on_blockhash_update(self, callback: Callable) -> None:
        """Set callback for blockhash updates"""
        self._on_blockhash_update = callback
    
    # ===== Account State Management =====
    
    def update_account(self, pubkey: str, state: AccountState) -> None:
        """Update account state in cache"""
        with self._lock:
            self._accounts[pubkey] = state
    
    def get_account(self, pubkey: str) -> Optional[AccountState]:
        """Get account state from cache - NO RPC CALL"""
        with self._lock:
            state = self._accounts.get(pubkey)
            if state and state.is_fresh(self.config.cache_ttl):
                return state
            return None
    
    def get_accounts(self, pubkeys: List[str]) -> Dict[str, AccountState]:
        """Get multiple account states - NO RPC CALL"""
        result = {}
        with self._lock:
            for pubkey in pubkeys:
                state = self._accounts.get(pubkey)
                if state and state.is_fresh(self.config.cache_ttl):
                    result[pubkey] = state
        return result
    
    async def prefetch_accounts(self, pubkeys: List[str]) -> None:
        """
        Prefetch accounts - RPC call happens here (before trading)
        Call this BEFORE entering the hot path
        """
        if not pubkeys:
            return
        
        try:
            accounts = await asyncio.wait_for(
                self.rpc_client.get_multiple_accounts(pubkeys),
                timeout=self.config.prefetch_timeout
            )
            
            for pubkey, account in zip(pubkeys, accounts):
                if account:
                    state = AccountState(
                        pubkey=pubkey,
                        data=account.get('data', b''),
                        lamports=account.get('lamports', 0),
                        owner=account.get('owner', ''),
                        executable=account.get('executable', False),
                        rent_epoch=account.get('rent_epoch', 0),
                        slot=account.get('slot', 0),
                    )
                    self.update_account(pubkey, state)
                    
        except Exception as e:
            with self._lock:
                self._metrics['prefetch_errors'] += 1
            raise
    
    # ===== Pool State Management =====
    
    def update_pool(self, pool_address: str, state: PoolState) -> None:
        """Update pool state in cache"""
        with self._lock:
            self._pools[pool_address] = state
    
    def get_pool(self, pool_address: str) -> Optional[PoolState]:
        """Get pool state from cache - NO RPC CALL"""
        with self._lock:
            state = self._pools.get(pool_address)
            if state and state.is_fresh(self.config.cache_ttl):
                return state
            return None
    
    # ===== Metrics =====
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get prefetch metrics"""
        with self._lock:
            return {
                **self._metrics,
                'accounts_cached': len(self._accounts),
                'pools_cached': len(self._pools),
                'data_fresh': self.is_data_fresh(),
            }


class TradingContext:
    """
    Trading context with all prefetched data needed for a trade.
    
    Created BEFORE hot path execution, contains all necessary state.
    NO RPC calls during trade execution.
    """
    
    def __init__(
        self,
        hot_path_state: HotPathState,
        payer: str,
    ):
        self.payer = payer
        self.created_at = time.time()
        
        # Get prefetched data - NO RPC
        blockhash, last_valid_height, valid = hot_path_state.get_blockhash()
        if not valid:
            raise ValueError("Stale or missing blockhash - prefetch required")
        
        self.blockhash = blockhash
        self.last_valid_height = last_valid_height
        
        # Account states (populated as needed)
        self.account_states: Dict[str, AccountState] = {}
        self.pool_states: Dict[str, PoolState] = {}
    
    def add_account(self, pubkey: str, hot_path_state: HotPathState) -> bool:
        """Add account state from cache"""
        state = hot_path_state.get_account(pubkey)
        if state:
            self.account_states[pubkey] = state
            return True
        return False
    
    def add_pool(self, pool_address: str, hot_path_state: HotPathState) -> bool:
        """Add pool state from cache"""
        state = hot_path_state.get_pool(pool_address)
        if state:
            self.pool_states[pool_address] = state
            return True
        return False
    
    def age(self) -> float:
        """Get age of context in seconds"""
        return time.time() - self.created_at
    
    def is_valid(self, max_age: float = 5.0) -> bool:
        """Check if context is still valid"""
        return self.age() <= max_age
    
    def get_token_account_data(self, pubkey: str) -> Optional[bytes]:
        """Get token account data from context"""
        state = self.account_states.get(pubkey)
        return state.data if state else None


# ===== Errors =====

class HotPathError(Exception):
    """Base error for hot path operations"""
    pass


class StaleBlockhashError(HotPathError):
    """Blockhash is stale or not available"""
    pass


class MissingAccountError(HotPathError):
    """Required account not in cache"""
    pass


class ContextExpiredError(HotPathError):
    """Trading context has expired"""
    pass


# ===== Type Aliases for Compatibility =====

AccountStateCache = AccountState
PoolStateCache = PoolState
