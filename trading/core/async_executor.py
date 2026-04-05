"""
Async executor for high-performance trading.

Provides async transaction submission with parallel execution,
backpressure handling, and comprehensive error handling.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Union
import logging

from ...swqos.providers import (
    SwqosClient,
    SwqosManager,
    SwqosType,
    TransactionResult,
    SwqosConfig,
)

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    """Execution status for transactions."""
    PENDING = auto()
    SUBMITTING = auto()
    SUBMITTED = auto()
    CONFIRMING = auto()
    CONFIRMED = auto()
    FAILED = auto()
    TIMEOUT = auto()
    CANCELLED = auto()


class SubmitMode(Enum):
    """Transaction submission mode."""
    SINGLE = auto()  # Submit to single best provider
    PARALLEL = auto()  # Submit to all providers in parallel
    FALLBACK = auto()  # Try providers in order until success
    BROADCAST = auto()  # Submit to all, wait for majority


@dataclass
class ExecutionConfig:
    """Configuration for async execution."""
    submit_mode: SubmitMode = SubmitMode.FALLBACK
    max_concurrent: int = 100
    timeout_ms: int = 30000
    confirmation_timeout_ms: int = 60000
    retry_attempts: int = 3
    retry_delay_ms: int = 100
    parallel_submit_count: int = 3  # Number of providers for parallel mode
    confirmation_check_interval_ms: int = 500
    enable_metrics: bool = True
    priority_fee_multiplier: float = 1.0
    skip_preflight: bool = True
    preflight_commitment: str = "processed"


@dataclass
class ExecutionResult:
    """Result of transaction execution."""
    signature: Optional[str]
    status: ExecutionStatus
    success: bool
    provider: Optional[str] = None
    submit_time_ms: int = 0
    confirm_time_ms: int = 0
    total_time_ms: int = 0
    attempts: int = 0
    error: Optional[str] = None
    slot: Optional[int] = None
    confirmations: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingExecution:
    """Internal state for pending execution."""
    transaction: bytes
    config: ExecutionConfig
    future: asyncio.Future
    start_time: float
    attempts: int = 0
    results: List[TransactionResult] = field(default_factory=list)


class AsyncTradeExecutor:
    """
    High-performance async trade executor.

    Features:
    - Parallel submission to multiple SWQoS providers
    - Configurable submission strategies
    - Backpressure handling
    - Comprehensive metrics
    """

    def __init__(
        self,
        swqos_manager: SwqosManager,
        config: Optional[ExecutionConfig] = None,
    ):
        self.swqos_manager = swqos_manager
        self.config = config or ExecutionConfig()
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent)
        self._pending: Dict[str, PendingExecution] = {}
        self._metrics = {
            "total_submitted": 0,
            "total_confirmed": 0,
            "total_failed": 0,
            "avg_submit_time_ms": 0,
            "avg_confirm_time_ms": 0,
        }
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the executor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("AsyncTradeExecutor started")

    async def stop(self) -> None:
        """Stop the executor."""
        self._running = False

        # Cancel all pending
        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.cancel()

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("AsyncTradeExecutor stopped")

    async def execute(
        self,
        transaction: bytes,
        config: Optional[ExecutionConfig] = None,
    ) -> ExecutionResult:
        """
        Execute a transaction asynchronously.

        Args:
            transaction: Serialized transaction bytes
            config: Optional execution config override

        Returns:
            Execution result
        """
        exec_config = config or self.config

        async with self._semaphore:
            start_time = time.time()

            if exec_config.submit_mode == SubmitMode.SINGLE:
                return await self._execute_single(transaction, exec_config)
            elif exec_config.submit_mode == SubmitMode.PARALLEL:
                return await self._execute_parallel(transaction, exec_config)
            elif exec_config.submit_mode == SubmitMode.FALLBACK:
                return await self._execute_fallback(transaction, exec_config)
            elif exec_config.submit_mode == SubmitMode.BROADCAST:
                return await self._execute_broadcast(transaction, exec_config)
            else:
                raise ValueError(f"Unknown submit mode: {exec_config.submit_mode}")

    async def execute_many(
        self,
        transactions: List[bytes],
        config: Optional[ExecutionConfig] = None,
    ) -> List[ExecutionResult]:
        """
        Execute multiple transactions.

        Args:
            transactions: List of serialized transactions
            config: Optional execution config override

        Returns:
            List of execution results
        """
        tasks = [
            self.execute(tx, config)
            for tx in transactions
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single(
        self,
        transaction: bytes,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """Execute using single best provider."""
        start_time = time.time()

        client = self.swqos_manager.get_best_client()
        if not client:
            return ExecutionResult(
                signature=None,
                status=ExecutionStatus.FAILED,
                success=False,
                error="No available providers",
                total_time_ms=int((time.time() - start_time) * 1000),
            )

        result = await self._submit_with_retry(
            client, transaction, config
        )

        total_time = int((time.time() - start_time) * 1000)

        return ExecutionResult(
            signature=result.signature if result.success else None,
            status=ExecutionStatus.CONFIRMED if result.success else ExecutionStatus.FAILED,
            success=result.success,
            provider=result.provider,
            submit_time_ms=result.latency_ms,
            total_time_ms=total_time,
            attempts=1,
            error=result.error,
            slot=result.slot,
        )

    async def _execute_parallel(
        self,
        transaction: bytes,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """Execute using parallel submission to multiple providers."""
        start_time = time.time()

        clients = self.swqos_manager.get_all_clients()
        if not clients:
            return ExecutionResult(
                signature=None,
                status=ExecutionStatus.FAILED,
                success=False,
                error="No available providers",
                total_time_ms=int((time.time() - start_time) * 1000),
            )

        # Limit parallel submissions
        clients = clients[:config.parallel_submit_count]

        # Create submission tasks
        tasks = [
            self._submit_single(client, transaction)
            for client in clients
        ]

        # Wait for first success or all failures
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
            timeout=config.timeout_ms / 1000,
        )

        # Cancel remaining tasks
        for task in pending:
            task.cancel()

        # Process results
        attempts = 0
        for task in done:
            try:
                result = task.result()
                attempts += 1
                if result.success:
                    total_time = int((time.time() - start_time) * 1000)
                    return ExecutionResult(
                        signature=result.signature,
                        status=ExecutionStatus.CONFIRMED,
                        success=True,
                        provider=result.provider,
                        submit_time_ms=result.latency_ms,
                        total_time_ms=total_time,
                        attempts=attempts,
                        slot=result.slot,
                    )
            except Exception:
                attempts += 1

        total_time = int((time.time() - start_time) * 1000)
        return ExecutionResult(
            signature=None,
            status=ExecutionStatus.FAILED,
            success=False,
            error="All parallel submissions failed",
            total_time_ms=total_time,
            attempts=attempts,
        )

    async def _execute_fallback(
        self,
        transaction: bytes,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """Execute using fallback strategy."""
        start_time = time.time()
        attempts = 0

        for _ in range(config.retry_attempts):
            result = await self.swqos_manager.submit_with_fallback(
                transaction,
                tip=0,  # Tip handled by config
            )
            attempts += 1

            if result.success:
                total_time = int((time.time() - start_time) * 1000)
                return ExecutionResult(
                    signature=result.signature,
                    status=ExecutionStatus.CONFIRMED,
                    success=True,
                    provider=result.provider,
                    submit_time_ms=result.latency_ms,
                    total_time_ms=total_time,
                    attempts=attempts,
                    slot=result.slot,
                )

            # Wait before retry
            if _ < config.retry_attempts - 1:
                await asyncio.sleep(config.retry_delay_ms / 1000)

        total_time = int((time.time() - start_time) * 1000)
        return ExecutionResult(
            signature=None,
            status=ExecutionStatus.FAILED,
            success=False,
            error="All fallback attempts failed",
            total_time_ms=total_time,
            attempts=attempts,
        )

    async def _execute_broadcast(
        self,
        transaction: bytes,
        config: ExecutionConfig,
    ) -> ExecutionResult:
        """Broadcast to all providers and wait for majority."""
        start_time = time.time()

        results = await self.swqos_manager.submit_to_all(transaction)

        successful = sum(
            1 for r in results.get("results", [])
            if isinstance(r, TransactionResult) and r.success
        )
        total = results.get("total", 0)

        # Majority success
        if successful > total / 2:
            # Use first successful result
            for r in results.get("results", []):
                if isinstance(r, TransactionResult) and r.success:
                    total_time = int((time.time() - start_time) * 1000)
                    return ExecutionResult(
                        signature=r.signature,
                        status=ExecutionStatus.CONFIRMED,
                        success=True,
                        provider=r.provider,
                        submit_time_ms=r.latency_ms,
                        total_time_ms=total_time,
                        attempts=total,
                        slot=r.slot,
                        details={"broadcast_success": successful, "broadcast_total": total},
                    )

        total_time = int((time.time() - start_time) * 1000)
        return ExecutionResult(
            signature=None,
            status=ExecutionStatus.FAILED,
            success=False,
            error=f"Broadcast failed: {successful}/{total} succeeded",
            total_time_ms=total_time,
            attempts=total,
            details={"broadcast_success": successful, "broadcast_total": total},
        )

    async def _submit_single(
        self,
        client: SwqosClient,
        transaction: bytes,
    ) -> TransactionResult:
        """Submit to a single client."""
        try:
            return await client.submit_transaction(transaction)
        except Exception as e:
            return TransactionResult(
                success=False,
                provider=client.config.swqos_type.value,
                error=str(e),
            )

    async def _submit_with_retry(
        self,
        client: SwqosClient,
        transaction: bytes,
        config: ExecutionConfig,
    ) -> TransactionResult:
        """Submit with retry logic."""
        last_error = None

        for attempt in range(config.retry_attempts):
            try:
                result = await asyncio.wait_for(
                    client.submit_transaction(transaction),
                    timeout=config.timeout_ms / 1000,
                )
                if result.success:
                    return result
                last_error = result.error
            except asyncio.TimeoutError:
                last_error = "Timeout"
            except Exception as e:
                last_error = str(e)

            if attempt < config.retry_attempts - 1:
                await asyncio.sleep(config.retry_delay_ms / 1000)

        return TransactionResult(
            success=False,
            provider=client.config.swqos_type.value,
            error=last_error or "All retries failed",
        )

    async def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                # Clean up completed futures
                completed = [
                    k for k, v in self._pending.items()
                    if v.future.done()
                ]
                for k in completed:
                    del self._pending[k]

                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get executor metrics."""
        return self._metrics.copy()

    def get_pending_count(self) -> int:
        """Get number of pending executions."""
        return len(self._pending)
