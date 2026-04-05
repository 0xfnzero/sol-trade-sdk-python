"""
Transaction pool for managing pending transactions.

Provides efficient queue management, prioritization, and
batching for high-throughput trading.
"""

from __future__ import annotations

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Callable
import logging

logger = logging.getLogger(__name__)


class TransactionStatus(Enum):
    """Status of a pooled transaction."""
    QUEUED = auto()
    PROCESSING = auto()
    SUBMITTED = auto()
    CONFIRMED = auto()
    FAILED = auto()
    EXPIRED = auto()
    DROPPED = auto()


@dataclass
class PoolConfig:
    """Configuration for transaction pool."""
    max_size: int = 10000
    max_pending: int = 1000
    default_ttl_ms: int = 60000
    cleanup_interval_ms: int = 5000
    enable_priority_queue: bool = True
    batch_size: int = 10
    batch_timeout_ms: int = 100
    priority_levels: int = 5


@dataclass
class PendingTransaction:
    """A transaction in the pool."""
    id: str
    transaction: bytes
    priority: int = 0
    status: TransactionStatus = TransactionStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    submitted_at: Optional[float] = None
    confirmed_at: Optional[float] = None
    signature: Optional[str] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.expires_at is None:
            self.expires_at = self.created_at + 60  # Default 60s TTL

    def __lt__(self, other: PendingTransaction) -> bool:
        # Higher priority = lower value for heap
        if self.priority != other.priority:
            return self.priority > other.priority
        # Earlier creation = higher priority
        return self.created_at < other.created_at

    def is_expired(self) -> bool:
        """Check if transaction has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def age_ms(self) -> int:
        """Get age in milliseconds."""
        return int((time.time() - self.created_at) * 1000)


@dataclass
class BatchResult:
    """Result of a batch submission."""
    batch_id: str
    transactions: List[str]  # Transaction IDs
    success: bool
    signatures: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    submit_time_ms: int = 0


class TransactionPool:
    """
    High-performance transaction pool.

    Features:
    - Priority queue with multiple levels
    - Automatic batching
    - TTL management
    - Backpressure handling
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig()
        self._queue: List[PendingTransaction] = []
        self._transactions: Dict[str, PendingTransaction] = {}
        self._processing: Set[str] = set()
        self._submitted: Dict[str, PendingTransaction] = {}
        self._confirmed: Dict[str, PendingTransaction] = {}
        self._failed: Dict[str, PendingTransaction] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(self.config.max_pending)
        self._batch_event = asyncio.Event()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        self._batch_task: Optional[asyncio.Task] = None
        self._metrics = {
            "queued": 0,
            "submitted": 0,
            "confirmed": 0,
            "failed": 0,
            "expired": 0,
            "dropped": 0,
        }

    async def start(self) -> None:
        """Start the pool."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._batch_task = asyncio.create_task(self._batch_loop())
        logger.info("TransactionPool started")

    async def stop(self) -> None:
        """Stop the pool."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if self._batch_task:
            self._batch_task.cancel()
            try:
                await self._batch_task
            except asyncio.CancelledError:
                pass

        logger.info("TransactionPool stopped")

    async def submit(
        self,
        transaction: bytes,
        priority: int = 0,
        ttl_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Submit a transaction to the pool.

        Args:
            transaction: Serialized transaction bytes
            priority: Priority level (higher = more urgent)
            ttl_ms: Time-to-live in milliseconds
            metadata: Optional metadata

        Returns:
            Transaction ID or None if pool is full
        """
        async with self._lock:
            if len(self._transactions) >= self.config.max_size:
                logger.warning("Transaction pool full, dropping transaction")
                self._metrics["dropped"] += 1
                return None

            tx_id = self._generate_id()
            now = time.time()
            expires = now + (ttl_ms or self.config.default_ttl_ms) / 1000

            pending = PendingTransaction(
                id=tx_id,
                transaction=transaction,
                priority=min(priority, self.config.priority_levels - 1),
                created_at=now,
                expires_at=expires,
                metadata=metadata or {},
            )

            self._transactions[tx_id] = pending
            heapq.heappush(self._queue, pending)
            self._metrics["queued"] += 1

            # Signal batch processor
            self._batch_event.set()

            return tx_id

    async def get_transaction(self, tx_id: str) -> Optional[PendingTransaction]:
        """Get transaction by ID."""
        async with self._lock:
            return self._transactions.get(tx_id)

    async def get_status(self, tx_id: str) -> Optional[TransactionStatus]:
        """Get transaction status."""
        tx = await self.get_transaction(tx_id)
        return tx.status if tx else None

    async def cancel(self, tx_id: str) -> bool:
        """Cancel a pending transaction."""
        async with self._lock:
            tx = self._transactions.get(tx_id)
            if not tx:
                return False

            if tx.status in (TransactionStatus.QUEUED, TransactionStatus.PROCESSING):
                tx.status = TransactionStatus.DROPPED
                self._processing.discard(tx_id)
                return True

            return False

    async def get_batch(self, max_size: Optional[int] = None) -> List[PendingTransaction]:
        """
        Get a batch of transactions for processing.

        Args:
            max_size: Maximum batch size

        Returns:
            List of pending transactions
        """
        size = max_size or self.config.batch_size
        batch: List[PendingTransaction] = []

        async with self._lock:
            while len(batch) < size and self._queue:
                tx = heapq.heappop(self._queue)

                if tx.is_expired():
                    tx.status = TransactionStatus.EXPIRED
                    self._metrics["expired"] += 1
                    continue

                if tx.status == TransactionStatus.QUEUED:
                    tx.status = TransactionStatus.PROCESSING
                    self._processing.add(tx.id)
                    batch.append(tx)

        return batch

    async def mark_submitted(
        self,
        tx_id: str,
        signature: str,
    ) -> None:
        """Mark transaction as submitted."""
        async with self._lock:
            tx = self._transactions.get(tx_id)
            if tx:
                tx.status = TransactionStatus.SUBMITTED
                tx.signature = signature
                tx.submitted_at = time.time()
                self._processing.discard(tx_id)
                self._submitted[tx_id] = tx
                self._metrics["submitted"] += 1
                self._metrics["queued"] -= 1

    async def mark_confirmed(self, tx_id: str) -> None:
        """Mark transaction as confirmed."""
        async with self._lock:
            tx = self._transactions.get(tx_id)
            if tx:
                tx.status = TransactionStatus.CONFIRMED
                tx.confirmed_at = time.time()
                self._submitted.pop(tx_id, None)
                self._confirmed[tx_id] = tx
                self._metrics["confirmed"] += 1

    async def mark_failed(self, tx_id: str, error: str) -> None:
        """Mark transaction as failed."""
        async with self._lock:
            tx = self._transactions.get(tx_id)
            if tx:
                tx.status = TransactionStatus.FAILED
                tx.error = error
                tx.attempts += 1
                self._processing.discard(tx_id)

                if tx.attempts < tx.max_attempts:
                    # Re-queue for retry
                    tx.status = TransactionStatus.QUEUED
                    heapq.heappush(self._queue, tx)
                else:
                    self._submitted.pop(tx_id, None)
                    self._failed[tx_id] = tx
                    self._metrics["failed"] += 1
                    self._metrics["queued"] -= 1

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            **self._metrics,
            "current_queued": len(self._queue),
            "current_processing": len(self._processing),
            "current_submitted": len(self._submitted),
            "current_confirmed": len(self._confirmed),
            "current_failed": len(self._failed),
            "total_transactions": len(self._transactions),
        }

    def _generate_id(self) -> str:
        """Generate unique transaction ID."""
        import uuid
        return str(uuid.uuid4())

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                await self._cleanup_expired()
                await asyncio.sleep(self.config.cleanup_interval_ms / 1000)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_expired(self) -> None:
        """Remove expired transactions."""
        async with self._lock:
            now = time.time()
            expired = [
                tx_id for tx_id, tx in self._transactions.items()
                if tx.is_expired() and tx.status == TransactionStatus.QUEUED
            ]

            for tx_id in expired:
                tx = self._transactions[tx_id]
                tx.status = TransactionStatus.EXPIRED
                self._metrics["expired"] += 1
                self._metrics["queued"] -= 1

    async def _batch_loop(self) -> None:
        """Background batch processing loop."""
        while self._running:
            try:
                # Wait for transactions or timeout
                try:
                    await asyncio.wait_for(
                        self._batch_event.wait(),
                        timeout=self.config.batch_timeout_ms / 1000,
                    )
                except asyncio.TimeoutError:
                    pass

                self._batch_event.clear()

                # Process batch if queue has items
                if self._queue:
                    batch = await self.get_batch()
                    if batch:
                        await self._process_batch(batch)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Batch loop error: {e}")

    async def _process_batch(self, batch: List[PendingTransaction]) -> None:
        """Process a batch of transactions."""
        # This would be implemented by the executor
        # For now, just log
        logger.debug(f"Processing batch of {len(batch)} transactions")


class PriorityCalculator:
    """Calculate transaction priority based on various factors."""

    @staticmethod
    def calculate(
        base_priority: int = 0,
        fee_priority: int = 0,
        time_in_pool_ms: int = 0,
        sender_reputation: float = 1.0,
    ) -> int:
        """
        Calculate transaction priority score.

        Args:
            base_priority: User-specified priority
            fee_priority: Priority based on fees paid
            time_in_pool_ms: Time spent in pool
            sender_reputation: Sender reputation score

        Returns:
            Priority score (higher = more urgent)
        """
        # Weight factors
        base_weight = 1.0
        fee_weight = 0.5
        time_weight = 0.1
        reputation_weight = 0.3

        # Calculate components
        time_bonus = min(time_in_pool_ms / 1000, 10)  # Max 10 points for waiting

        score = (
            base_priority * base_weight +
            fee_priority * fee_weight +
            time_bonus * time_weight +
            sender_reputation * 10 * reputation_weight
        )

        return int(score)
