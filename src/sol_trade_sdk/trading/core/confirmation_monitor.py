"""
Confirmation monitoring for transactions.

Provides real-time tracking of transaction confirmation status
with configurable confirmation levels.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set
import logging

logger = logging.getLogger(__name__)


class ConfirmationStatus(Enum):
    """Transaction confirmation status."""
    PENDING = auto()
    PROCESSED = auto()
    CONFIRMED = auto()
    FINALIZED = auto()
    FAILED = auto()
    TIMEOUT = auto()
    DROPPED = auto()


@dataclass
class ConfirmationConfig:
    """Configuration for confirmation monitoring."""
    commitment: str = "confirmed"  # processed, confirmed, finalized
    poll_interval_ms: int = 500
    timeout_ms: int = 60000
    max_polls: int = 120
    enable_websocket: bool = True
    enable_rpc_fallback: bool = True
    confirmation_callback: Optional[Callable[[str, ConfirmationStatus], None]] = None


@dataclass
class ConfirmationState:
    """State of a confirmation check."""
    signature: str
    status: ConfirmationStatus
    slot: Optional[int] = None
    confirmations: int = 0
    err: Optional[Dict[str, Any]] = None
    last_check: float = field(default_factory=time.time)
    check_count: int = 0


@dataclass
class ConfirmationResult:
    """Result of confirmation monitoring."""
    signature: str
    status: ConfirmationStatus
    success: bool
    slot: Optional[int] = None
    confirmations: int = 0
    error: Optional[str] = None
    confirmation_time_ms: int = 0
    total_checks: int = 0


class ConfirmationMonitor:
    """
    Monitor transaction confirmations.

    Features:
    - Multi-level commitment tracking
    - WebSocket and RPC polling
    - Batch status checking
    - Configurable timeouts
    """

    def __init__(
        self,
        rpc_client: Any,  # AsyncClient or similar
        config: Optional[ConfirmationConfig] = None,
    ):
        self.rpc_client = rpc_client
        self.config = config or ConfirmationConfig()
        self._tracked: Dict[str, ConfirmationState] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._websocket_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_tracked": 0,
            "confirmed": 0,
            "failed": 0,
            "timeouts": 0,
            "avg_confirmation_time_ms": 0,
        }

    async def start(self) -> None:
        """Start the monitor."""
        self._running = True
        self._monitor_task = asyncio.create_task(self._poll_loop())

        if self.config.enable_websocket:
            self._websocket_task = asyncio.create_task(self._websocket_loop())

        logger.info("ConfirmationMonitor started")

    async def stop(self) -> None:
        """Stop the monitor."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._websocket_task:
            self._websocket_task.cancel()
            try:
                await self._websocket_task
            except asyncio.CancelledError:
                pass

        logger.info("ConfirmationMonitor stopped")

    async def track(
        self,
        signature: str,
        callback: Optional[Callable[[ConfirmationResult], None]] = None,
    ) -> None:
        """
        Start tracking a transaction signature.

        Args:
            signature: Transaction signature
            callback: Optional callback on status change
        """
        async with self._lock:
            self._tracked[signature] = ConfirmationState(
                signature=signature,
                status=ConfirmationStatus.PENDING,
            )

            if callback:
                if signature not in self._callbacks:
                    self._callbacks[signature] = []
                self._callbacks[signature].append(callback)

            self._metrics["total_tracked"] += 1

    async def untrack(self, signature: str) -> None:
        """Stop tracking a signature."""
        async with self._lock:
            self._tracked.pop(signature, None)
            self._callbacks.pop(signature, None)

    async def get_status(self, signature: str) -> Optional[ConfirmationStatus]:
        """Get current confirmation status."""
        async with self._lock:
            state = self._tracked.get(signature)
            return state.status if state else None

    async def wait_for_confirmation(
        self,
        signature: str,
        target_status: ConfirmationStatus = ConfirmationStatus.CONFIRMED,
        timeout_ms: Optional[int] = None,
    ) -> ConfirmationResult:
        """
        Wait for transaction to reach target confirmation status.

        Args:
            signature: Transaction signature
            target_status: Target status to wait for
            timeout_ms: Optional timeout override

        Returns:
            Confirmation result
        """
        timeout = timeout_ms or self.config.timeout_ms
        start_time = time.time()

        # Start tracking if not already
        await self.track(signature)

        while True:
            async with self._lock:
                state = self._tracked.get(signature)

            if not state:
                return ConfirmationResult(
                    signature=signature,
                    status=ConfirmationStatus.DROPPED,
                    success=False,
                    error="Tracking stopped",
                )

            # Check if reached target
            if self._status_reached(state.status, target_status):
                elapsed = int((time.time() - start_time) * 1000)
                return ConfirmationResult(
                    signature=signature,
                    status=state.status,
                    success=state.status != ConfirmationStatus.FAILED,
                    slot=state.slot,
                    confirmations=state.confirmations,
                    error=str(state.err) if state.err else None,
                    confirmation_time_ms=elapsed,
                    total_checks=state.check_count,
                )

            # Check timeout
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms > timeout:
                return ConfirmationResult(
                    signature=signature,
                    status=ConfirmationStatus.TIMEOUT,
                    success=False,
                    error=f"Timeout after {elapsed_ms:.0f}ms",
                    total_checks=state.check_count if state else 0,
                )

            # Wait before next check
            await asyncio.sleep(self.config.poll_interval_ms / 1000)

    async def check_now(self, signatures: Optional[List[str]] = None) -> None:
        """Force immediate status check."""
        async with self._lock:
            sigs = signatures or list(self._tracked.keys())

        if not sigs:
            return

        try:
            statuses = await self._fetch_statuses(sigs)

            async with self._lock:
                for sig, status_info in statuses.items():
                    if sig in self._tracked:
                        await self._update_status(sig, status_info)

        except Exception as e:
            logger.error(f"Status check failed: {e}")

    def _status_reached(
        self,
        current: ConfirmationStatus,
        target: ConfirmationStatus,
    ) -> bool:
        """Check if current status meets or exceeds target."""
        levels = [
            ConfirmationStatus.PENDING,
            ConfirmationStatus.PROCESSED,
            ConfirmationStatus.CONFIRMED,
            ConfirmationStatus.FINALIZED,
        ]

        if current == ConfirmationStatus.FAILED:
            return True

        try:
            current_idx = levels.index(current)
            target_idx = levels.index(target)
            return current_idx >= target_idx
        except ValueError:
            return False

    async def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                async with self._lock:
                    signatures = list(self._tracked.keys())

                if signatures:
                    await self.check_now(signatures)

                await asyncio.sleep(self.config.poll_interval_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Poll loop error: {e}")

    async def _websocket_loop(self) -> None:
        """WebSocket subscription loop."""
        # Placeholder for WebSocket implementation
        # Would subscribe to signature notifications
        while self._running:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    async def _fetch_statuses(
        self,
        signatures: List[str],
    ) -> Dict[str, Any]:
        """Fetch statuses from RPC."""
        # This would use the actual RPC client
        # Placeholder implementation
        return {}

    async def _update_status(
        self,
        signature: str,
        status_info: Any,
    ) -> None:
        """Update status from RPC response."""
        state = self._tracked.get(signature)
        if not state:
            return

        # Parse status info and update state
        # Placeholder logic
        new_status = self._parse_status(status_info)

        if new_status != state.status:
            state.status = new_status
            state.last_check = time.time()
            state.check_count += 1

            # Notify callbacks
            await self._notify_callbacks(signature, new_status)

            # Update metrics
            if new_status == ConfirmationStatus.CONFIRMED:
                self._metrics["confirmed"] += 1
            elif new_status == ConfirmationStatus.FAILED:
                self._metrics["failed"] += 1

    def _parse_status(self, status_info: Any) -> ConfirmationStatus:
        """Parse RPC status response."""
        # Placeholder - would parse actual RPC response
        return ConfirmationStatus.PENDING

    async def _notify_callbacks(
        self,
        signature: str,
        status: ConfirmationStatus,
    ) -> None:
        """Notify registered callbacks."""
        callbacks = self._callbacks.get(signature, [])

        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signature, status)
                else:
                    callback(signature, status)
            except Exception as e:
                logger.error(f"Callback error: {e}")

        # Global callback
        if self.config.confirmation_callback:
            try:
                self.config.confirmation_callback(signature, status)
            except Exception as e:
                logger.error(f"Global callback error: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get monitor metrics."""
        return self._metrics.copy()

    def get_tracked_count(self) -> int:
        """Get number of tracked signatures."""
        return len(self._tracked)


class MultiConfirmationMonitor:
    """Monitor multiple transactions simultaneously."""

    def __init__(self, monitor: ConfirmationMonitor):
        self.monitor = monitor

    async def wait_for_all(
        self,
        signatures: List[str],
        target_status: ConfirmationStatus = ConfirmationStatus.CONFIRMED,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, ConfirmationResult]:
        """
        Wait for all signatures to confirm.

        Returns:
            Dict mapping signatures to results
        """
        tasks = [
            self.monitor.wait_for_confirmation(sig, target_status, timeout_ms)
            for sig in signatures
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            sig: result if isinstance(result, ConfirmationResult) else ConfirmationResult(
                signature=sig,
                status=ConfirmationStatus.FAILED,
                success=False,
                error=str(result),
            )
            for sig, result in zip(signatures, results)
        }

    async def wait_for_any(
        self,
        signatures: List[str],
        target_status: ConfirmationStatus = ConfirmationStatus.CONFIRMED,
        timeout_ms: Optional[int] = None,
    ) -> ConfirmationResult:
        """
        Wait for any signature to confirm.

        Returns:
            First confirmed result
        """
        tasks = [
            self.monitor.wait_for_confirmation(sig, target_status, timeout_ms)
            for sig in signatures
        ]

        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel remaining
        for task in pending:
            task.cancel()

        # Return first result
        for task in done:
            try:
                return task.result()
            except Exception as e:
                return ConfirmationResult(
                    signature="",
                    status=ConfirmationStatus.FAILED,
                    success=False,
                    error=str(e),
                )

        return ConfirmationResult(
            signature="",
            status=ConfirmationStatus.FAILED,
            success=False,
            error="No results",
        )

    async def wait_for_majority(
        self,
        signatures: List[str],
        target_status: ConfirmationStatus = ConfirmationStatus.CONFIRMED,
        timeout_ms: Optional[int] = None,
    ) -> Dict[str, ConfirmationResult]:
        """
        Wait for majority of signatures to confirm.

        Returns:
            Results once majority is reached
        """
        results = await self.wait_for_all(signatures, target_status, timeout_ms)

        successful = sum(1 for r in results.values() if r.success)
        majority = len(signatures) // 2 + 1

        if successful >= majority:
            return results

        # Not enough succeeded
        for sig, result in results.items():
            if not result.success and not result.error:
                results[sig] = ConfirmationResult(
                    signature=sig,
                    status=ConfirmationStatus.FAILED,
                    success=False,
                    error="Majority not reached",
                )

        return results
