"""
Hot Path Executor for Sol Trade SDK

Executes trades with ZERO RPC calls in the hot path.
All data must be prefetched before execution.

Key principle: Prepare everything, then execute with minimal latency.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
import threading

try:
    from .state import (
        HotPathState,
        HotPathConfig,
        TradingContext,
        StaleBlockhashError,
        HotPathError,
    )
except ImportError:
    from state import (
        HotPathState,
        HotPathConfig,
        TradingContext,
        StaleBlockhashError,
        HotPathError,
    )

try:
    from solders.transaction import VersionedTransaction
    from solders.signature import Signature
    HAS_SOLDERS = True
except ImportError:
    HAS_SOLDERS = False


@dataclass
class ExecuteOptions:
    """Options for hot path execution"""
    parallel_submit: bool = True
    timeout: float = 10.0  # seconds
    skip_blockhash_validation: bool = False
    max_retries: int = 3


@dataclass
class ExecuteResult:
    """Result of hot path execution"""
    signature: str = ""
    success: bool = False
    error: Optional[str] = None
    latency_ms: int = 0
    swqos_type: str = ""
    blockhash_used: str = ""


class HotPathMetrics:
    """Thread-safe metrics collector"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self._total_trades = 0
        self._success_trades = 0
        self._failed_trades = 0
        self._total_latency_ms = 0
    
    def record(self, success: bool, latency_ms: int) -> None:
        with self._lock:
            self._total_trades += 1
            if success:
                self._success_trades += 1
            else:
                self._failed_trades += 1
            self._total_latency_ms += latency_ms
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            avg_latency = (
                self._total_latency_ms / self._total_trades 
                if self._total_trades > 0 else 0
            )
            return {
                'total_trades': self._total_trades,
                'success_trades': self._success_trades,
                'failed_trades': self._failed_trades,
                'total_latency_ms': self._total_latency_ms,
                'avg_latency_ms': avg_latency,
            }


class HotPathExecutor:
    """
    Executes trades with ZERO RPC calls in the hot path.
    
    Usage:
        1. Create executor with RPC client
        2. Call start() to begin background prefetching
        3. Prefetch required accounts/pools BEFORE trading
        4. Build transaction with prefetched blockhash
        5. Execute - no RPC calls during this phase
    
    All latency-sensitive operations use cached data.
    """
    
    def __init__(
        self,
        rpc_client: Any,
        config: Optional[HotPathConfig] = None,
    ):
        self.config = config or HotPathConfig()
        self.state = HotPathState(rpc_client, config)
        self.rpc_client = rpc_client
        
        # SWQoS clients for transaction submission
        self._swqos_clients: List[Any] = []  # List of SwqosClient
        self._clients_lock = threading.Lock()
        
        # Metrics
        self._metrics = HotPathMetrics()
    
    def add_swqos_client(self, client: Any) -> None:
        """Add a SWQoS client for transaction submission"""
        with self._clients_lock:
            self._swqos_clients.append(client)
    
    def remove_swqos_client(self, swqos_type: str) -> None:
        """Remove a SWQoS client"""
        with self._clients_lock:
            self._swqos_clients = [
                c for c in self._swqos_clients 
                if c.swqos_type != swqos_type
            ]
    
    async def start(self) -> None:
        """Start background prefetching"""
        await self.state.start()
    
    async def stop(self) -> None:
        """Stop background prefetching"""
        await self.state.stop()
    
    def get_state(self) -> HotPathState:
        """Get hot path state for external access"""
        return self.state
    
    def is_ready(self) -> bool:
        """Check if executor is ready for hot path execution"""
        return self.state.is_data_fresh() and len(self._swqos_clients) > 0
    
    async def wait_for_ready(
        self, 
        check_interval: float = 0.1,
        timeout: float = 30.0,
    ) -> bool:
        """Wait until executor is ready"""
        start = time.time()
        while time.time() - start < timeout:
            if self.is_ready():
                return True
            await asyncio.sleep(check_interval)
        return False
    
    async def prefetch_accounts(self, pubkeys: List[str]) -> None:
        """
        Prefetch accounts - call BEFORE hot path execution
        """
        await self.state.prefetch_accounts(pubkeys)
    
    def create_trading_context(self, payer: str) -> TradingContext:
        """
        Create trading context with prefetched data - NO RPC
        """
        return TradingContext(self.state, payer)
    
    async def execute(
        self,
        trade_type: str,
        transaction_bytes: bytes,
        opts: Optional[ExecuteOptions] = None,
    ) -> ExecuteResult:
        """
        Execute a pre-signed transaction - NO RPC CALLS
        
        Transaction must already be signed with valid blockhash.
        All state should be prefetched before calling this.
        """
        opts = opts or ExecuteOptions()
        start_time = time.time()
        
        # Validate blockhash is fresh (no RPC, just check cache age)
        if not opts.skip_blockhash_validation and not self.state.is_data_fresh():
            return ExecuteResult(
                success=False,
                error="Stale blockhash - prefetch required",
            )
        
        # Get clients
        with self._clients_lock:
            clients = list(self._swqos_clients)
        
        if not clients:
            return ExecuteResult(
                success=False,
                error="No SWQoS clients configured",
            )
        
        # Submit transaction
        result: ExecuteResult
        if opts.parallel_submit and len(clients) > 1:
            result = await self._execute_parallel(
                trade_type, transaction_bytes, clients, opts
            )
        else:
            result = await self._execute_sequential(
                trade_type, transaction_bytes, clients, opts
            )
        
        result.latency_ms = int((time.time() - start_time) * 1000)
        
        # Update metrics
        self._metrics.record(result.success, result.latency_ms)
        
        return result
    
    async def _execute_parallel(
        self,
        trade_type: str,
        tx_bytes: bytes,
        clients: List[Any],
        opts: ExecuteOptions,
    ) -> ExecuteResult:
        """Submit to all SWQoS clients in parallel - NO RPC

        Security fixes applied:
        - Proper task creation with asyncio.create_task
        - Proper cleanup of remaining tasks
        - Exception handling with context preservation
        """

        async def submit_to_client(client: Any) -> ExecuteResult:
            try:
                sig = await asyncio.wait_for(
                    client.send_transaction(trade_type, tx_bytes, False),
                    timeout=opts.timeout,
                )
                return ExecuteResult(
                    signature=sig,
                    success=True,
                    swqos_type=client.swqos_type,
                )
            except asyncio.TimeoutError:
                return ExecuteResult(
                    success=False,
                    error=f"Timeout after {opts.timeout}s",
                    swqos_type=getattr(client, 'swqos_type', 'unknown'),
                )
            except Exception as e:
                return ExecuteResult(
                    success=False,
                    error=f"{type(e).__name__}: {str(e)}",
                    swqos_type=getattr(client, 'swqos_type', 'unknown'),
                )

        # Create proper asyncio Tasks (not just coroutines)
        tasks = [asyncio.create_task(submit_to_client(c)) for c in clients]

        try:
            # Use asyncio.as_completed for first-success-wins
            for coro in asyncio.as_completed(tasks):
                result = await coro
                if result.success:
                    # Cancel remaining tasks
                    for task in tasks:
                        if not task.done():
                            task.cancel()
                    # Wait for cancellations to complete (with timeout)
                    try:
                        await asyncio.wait_for(
                            asyncio.gather(*tasks, return_exceptions=True),
                            timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        pass  # Some tasks didn't cancel in time
                    return result
        except Exception as e:
            # Cancel all tasks on error
            for task in tasks:
                if not task.done():
                    task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                pass
            return ExecuteResult(success=False, error=f"Execution error: {type(e).__name__}: {str(e)}")
        finally:
            # Ensure all tasks are cleaned up
            for task in tasks:
                if not task.done():
                    task.cancel()

        # All failed - gather all errors
        errors = []
        for task in tasks:
            if task.done() and not task.cancelled():
                try:
                    result = task.result()
                    if not result.success:
                        errors.append(f"{result.swqos_type}: {result.error}")
                except Exception as e:
                    errors.append(f"Exception: {str(e)}")

        error_msg = "All parallel submissions failed"
        if errors:
            error_msg += f" | Errors: {'; '.join(errors[:3])}"

        return ExecuteResult(
            success=False,
            error=error_msg,
        )
    
    async def _execute_sequential(
        self,
        trade_type: str,
        tx_bytes: bytes,
        clients: List[Any],
        opts: ExecuteOptions,
    ) -> ExecuteResult:
        """Submit to SWQoS clients sequentially - NO RPC"""
        
        last_error = "No clients available"
        
        for retry in range(opts.max_retries):
            for client in clients:
                try:
                    sig = await asyncio.wait_for(
                        client.send_transaction(trade_type, tx_bytes, False),
                        timeout=opts.timeout,
                    )
                    return ExecuteResult(
                        signature=sig,
                        success=True,
                        swqos_type=client.swqos_type,
                    )
                except Exception as e:
                    last_error = str(e)
        
        return ExecuteResult(
            success=False,
            error=f"All sequential submissions failed after {opts.max_retries} retries: {last_error}",
        )
    
    async def execute_multiple(
        self,
        trade_type: str,
        transactions: List[bytes],
        opts: Optional[ExecuteOptions] = None,
    ) -> List[ExecuteResult]:
        """Execute multiple transactions in parallel"""
        opts = opts or ExecuteOptions()
        tasks = [
            self.execute(trade_type, tx, opts) 
            for tx in transactions
        ]
        return await asyncio.gather(*tasks)
    
    def get_blockhash(self) -> Tuple[Optional[str], int, bool]:
        """
        Get cached blockhash - NO RPC CALL
        Use this to build transactions before execution
        """
        return self.state.get_blockhash()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get execution metrics"""
        return self._metrics.get_stats()


# ===== Transaction Builder Helper =====

class TransactionBuilder:
    """
    Builds transactions using prefetched data - NO RPC CALLS
    
    Use this to construct transactions before hot path execution.
    """
    
    def __init__(self, executor: HotPathExecutor):
        self.executor = executor
    
    def build_transaction(
        self,
        payer: str,
        instructions: List[Any],
        signers: List[Any],
        gas_config: Optional[Dict[str, int]] = None,
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Build a transaction using prefetched blockhash - NO RPC
        
        Returns:
            Tuple of (transaction_bytes, error_message)
        """
        # Get blockhash from cache
        blockhash, last_valid_height, valid = self.executor.get_blockhash()
        if not valid:
            return None, "Stale blockhash - prefetch required"
        
        # Transaction building would use solders/solana-py
        # This is a placeholder - actual implementation depends on
        # the transaction library being used
        
        # The key point is: NO RPC CALLS HERE
        # blockhash comes from cache
        
        return None, "Transaction building requires solders/solana-py integration"


# ===== Convenience Factory =====

def create_hot_path_executor(
    rpc_url: str,
    swqos_clients: Optional[List[Any]] = None,
    config: Optional[HotPathConfig] = None,
) -> HotPathExecutor:
    """
    Create a hot path executor with default configuration.
    
    Usage:
        executor = create_hot_path_executor(
            rpc_url="https://api.mainnet-beta.solana.com",
            swqos_clients=[jito_client, bloxroute_client],
        )
        await executor.start()
        
        # Prefetch required data
        await executor.prefetch_accounts([token_account_pubkey])
        
        # Now ready for hot path execution
        result = await executor.execute("buy", tx_bytes)
    """
    try:
        from ..rpc.client import AsyncRPCClient
    except ImportError:
        from rpc.client import AsyncRPCClient

    rpc_client = AsyncRPCClient(rpc_url)
    executor = HotPathExecutor(rpc_client, config)
    
    if swqos_clients:
        for client in swqos_clients:
            executor.add_swqos_client(client)
    
    return executor
