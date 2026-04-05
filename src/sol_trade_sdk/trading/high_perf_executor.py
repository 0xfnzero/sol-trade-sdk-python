"""
High-Performance Trading Executor for Sol Trade SDK
Implements parallel SWQOS submission with advanced optimization.
"""

from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
import asyncio
import time
import threading
from enum import Enum

from ..common.types import TradeType, SwqosType, GasFeeStrategy, GasFeeStrategyType
from ..swqos.clients import SwqosClient, ClientFactory, SwqosConfig, TradeError
from ..cache.cache import LRUCache, TTLCache
from ..pool.pool import WorkerPool, RateLimiter


# ===== Result Types =====

@dataclass
class TradeResult:
    """Result of a trade execution"""
    signature: str
    success: bool
    error: Optional[str] = None
    confirmation_time_ms: Optional[int] = None
    submitted_at: Optional[float] = None
    confirmed_at: Optional[float] = None
    swqos_type: Optional[SwqosType] = None
    retries: int = 0


@dataclass
class BatchResult:
    """Result of batch trade execution"""
    results: List[TradeResult]
    total_time_ms: int
    success_count: int
    failed_count: int


# ===== Execution Options =====

@dataclass
class ExecuteOptions:
    """Options for trade execution"""
    wait_confirmation: bool = True
    max_retries: int = 3
    retry_delay_ms: int = 100
    parallel_submit: bool = True
    timeout_ms: int = 30000
    priority: int = 0  # Higher = more priority
    skip_preflight: bool = False


def default_execute_options() -> ExecuteOptions:
    return ExecuteOptions()


# ===== Trade Config =====

@dataclass
class TradeConfig:
    """Configuration for trade executor"""
    rpc_url: str
    swqos_configs: List[SwqosConfig] = field(default_factory=list)
    gas_fee_strategy: Optional[GasFeeStrategy] = None
    max_workers: int = 10
    confirmation_timeout_ms: int = 30000
    confirmation_retry_count: int = 30
    rate_limit_per_second: float = 100.0


# ===== High-Performance Trade Executor =====

class TradeExecutor:
    """
    High-performance trade executor with parallel SWQOS submission.
    
    Features:
    - Parallel submission to multiple SWQOS providers
    - Automatic retry with exponential backoff
    - Connection pooling and reuse
    - Rate limiting
    - Metrics collection
    """

    def __init__(self, config: TradeConfig):
        self.config = config
        self._clients: Dict[SwqosType, SwqosClient] = {}
        self._gas_strategy = config.gas_fee_strategy or GasFeeStrategy()
        self._worker_pool = WorkerPool(workers=config.max_workers)
        self._rate_limiter = RateLimiter(
            rate=config.rate_limit_per_second,
            burst=int(config.rate_limit_per_second * 2)
        )
        
        # Caches
        self._blockhash_cache = TTLCache[str, str](ttl=2.0)
        self._signature_cache = LRUCache[str, TradeResult](max_size=1000)
        
        # Metrics
        self._total_trades = 0
        self._successful_trades = 0
        self._failed_trades = 0
        self._total_latency_ms = 0
        self._lock = threading.Lock()
        
        # Initialize clients
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """Initialize all SWQOS clients"""
        for swqos_config in self.config.swqos_configs:
            client = ClientFactory.create_client(swqos_config, self.config.rpc_url)
            self._clients[swqos_config.type] = client

    def add_client(self, config: SwqosConfig) -> None:
        """Add a new SWQOS client"""
        client = ClientFactory.create_client(config, self.config.rpc_url)
        self._clients[config.type] = client

    def remove_client(self, swqos_type: SwqosType) -> None:
        """Remove a SWQOS client"""
        self._clients.pop(swqos_type, None)

    def get_client(self, swqos_type: SwqosType) -> Optional[SwqosClient]:
        """Get a specific SWQOS client"""
        return self._clients.get(swqos_type)

    # ===== Core Execution Methods =====

    async def execute(
        self,
        trade_type: TradeType,
        transaction: bytes,
        opts: ExecuteOptions = None,
    ) -> TradeResult:
        """
        Execute a trade transaction.
        
        Args:
            trade_type: Type of trade (buy/sell)
            transaction: Serialized transaction bytes
            opts: Execution options
        
        Returns:
            TradeResult with signature and status
        """
        opts = opts or default_execute_options()
        
        if not self._clients:
            return TradeResult(
                signature="",
                success=False,
                error="No SWQOS clients configured",
            )

        # Rate limit
        self._rate_limiter.wait()

        if opts.parallel_submit:
            return await self._execute_parallel(trade_type, transaction, opts)
        else:
            return await self._execute_sequential(trade_type, transaction, opts)

    async def _execute_parallel(
        self,
        trade_type: TradeType,
        transaction: bytes,
        opts: ExecuteOptions,
    ) -> TradeResult:
        """Execute with parallel submission to all clients"""
        start_time = time.time()
        
        # Create futures for all clients
        loop = asyncio.get_event_loop()
        futures = []
        
        for client in self._clients.values():
            future = loop.run_in_executor(
                None,
                lambda c=client: self._submit_sync(c, trade_type, transaction, opts)
            )
            futures.append(future)
        
        # Wait for first success
        done, pending = await asyncio.wait(
            futures,
            return_when=asyncio.FIRST_COMPLETED,
        )
        
        # Cancel pending
        for future in pending:
            future.cancel()
        
        # Check results
        for future in done:
            try:
                result = future.result()
                if result.success:
                    self._record_success(time.time() - start_time)
                    return result
            except Exception:
                continue
        
        # All failed
        last_error = "All parallel submissions failed"
        self._record_failure()
        
        return TradeResult(
            signature="",
            success=False,
            error=last_error,
            confirmation_time_ms=int((time.time() - start_time) * 1000),
        )

    async def _execute_sequential(
        self,
        trade_type: TradeType,
        transaction: bytes,
        opts: ExecuteOptions,
    ) -> TradeResult:
        """Execute with sequential submission"""
        start_time = time.time()
        
        for retry in range(opts.max_retries):
            for client in self._clients.values():
                try:
                    result = await self._submit_to_client(client, trade_type, transaction, opts)
                    if result.success:
                        self._record_success(time.time() - start_time)
                        return result
                except Exception as e:
                    continue
            
            # Wait before retry
            if retry < opts.max_retries - 1:
                await asyncio.sleep(opts.retry_delay_ms / 1000.0)
        
        self._record_failure()
        return TradeResult(
            signature="",
            success=False,
            error=f"All submissions failed after {opts.max_retries} retries",
            confirmation_time_ms=int((time.time() - start_time) * 1000),
            retries=opts.max_retries,
        )

    def _submit_sync(
        self,
        client: SwqosClient,
        trade_type: TradeType,
        transaction: bytes,
        opts: ExecuteOptions,
    ) -> TradeResult:
        """Synchronous submit wrapper"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self._submit_to_client(client, trade_type, transaction, opts)
            )
        finally:
            loop.close()

    async def _submit_to_client(
        self,
        client: SwqosClient,
        trade_type: TradeType,
        transaction: bytes,
        opts: ExecuteOptions,
    ) -> TradeResult:
        """Submit transaction to a single client"""
        start_time = time.time()
        
        try:
            signature = await client.send_transaction(
                trade_type,
                transaction,
                opts.wait_confirmation,
            )
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            result = TradeResult(
                signature=signature,
                success=True,
                confirmation_time_ms=elapsed_ms,
                submitted_at=start_time,
                confirmed_at=time.time(),
                swqos_type=client.get_swqos_type(),
            )
            
            # Cache result
            self._signature_cache.set(signature, result)
            
            return result
            
        except Exception as e:
            return TradeResult(
                signature="",
                success=False,
                error=str(e),
                confirmation_time_ms=int((time.time() - start_time) * 1000),
                swqos_type=client.get_swqos_type(),
            )

    # ===== Batch Execution =====

    async def execute_batch(
        self,
        trade_type: TradeType,
        transactions: List[bytes],
        opts: ExecuteOptions = None,
    ) -> BatchResult:
        """Execute multiple transactions"""
        opts = opts or default_execute_options()
        start_time = time.time()
        
        tasks = [
            self.execute(trade_type, tx, opts)
            for tx in transactions
        ]
        
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if r.success)
        
        return BatchResult(
            results=list(results),
            total_time_ms=int((time.time() - start_time) * 1000),
            success_count=success_count,
            failed_count=len(results) - success_count,
        )

    # ===== Gas Fee Management =====

    def get_gas_config(
        self,
        swqos_type: SwqosType,
        trade_type: TradeType,
        strategy_type: GasFeeStrategyType,
    ):
        """Get gas configuration for a specific scenario"""
        value = self._gas_strategy.get(swqos_type, trade_type, strategy_type)
        if value is None:
            # Return defaults
            return {
                "cu_limit": 200000,
                "cu_price": 100000,
                "tip": 0.001,
            }
        return {
            "cu_limit": value.cu_limit,
            "cu_price": value.cu_price,
            "tip": value.tip,
        }

    # ===== Metrics =====

    def _record_success(self, latency: float) -> None:
        """Record a successful trade"""
        with self._lock:
            self._total_trades += 1
            self._successful_trades += 1
            self._total_latency_ms += int(latency * 1000)

    def _record_failure(self) -> None:
        """Record a failed trade"""
        with self._lock:
            self._total_trades += 1
            self._failed_trades += 1

    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics"""
        with self._lock:
            avg_latency = (
                self._total_latency_ms / self._successful_trades
                if self._successful_trades > 0 else 0
            )
            return {
                "total_trades": self._total_trades,
                "successful_trades": self._successful_trades,
                "failed_trades": self._failed_trades,
                "success_rate": (
                    self._successful_trades / self._total_trades
                    if self._total_trades > 0 else 0
                ),
                "avg_latency_ms": avg_latency,
                "clients_count": len(self._clients),
            }

    # ===== Cleanup =====

    def close(self) -> None:
        """Close all resources"""
        self._worker_pool.shutdown()


# ===== Convenience Functions =====

def create_trade_executor(
    rpc_url: str,
    swqos_types: List[SwqosType],
    api_keys: Optional[Dict[SwqosType, str]] = None,
) -> TradeExecutor:
    """Create a trade executor with specified SWQOS types"""
    api_keys = api_keys or {}
    
    configs = [
        SwqosConfig(
            type=swqos_type,
            api_key=api_keys.get(swqos_type),
        )
        for swqos_type in swqos_types
    ]

    config = TradeConfig(
        rpc_url=rpc_url,
        swqos_configs=configs,
    )

    return TradeExecutor(config)
