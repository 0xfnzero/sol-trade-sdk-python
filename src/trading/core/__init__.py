"""
Trading core module for Sol Trade SDK.

Provides core trading functionality:
- Async transaction execution
- Transaction pool management
- Confirmation monitoring
- Error handling and retry logic
"""

from .async_executor import (
    AsyncTradeExecutor,
    ExecutionConfig,
    ExecutionResult,
    ExecutionStatus,
    SubmitMode,
)

from .transaction_pool import (
    TransactionPool,
    PoolConfig,
    PendingTransaction,
    TransactionStatus,
    PriorityCalculator,
)

from .confirmation_monitor import (
    ConfirmationMonitor,
    ConfirmationConfig,
    ConfirmationStatus,
    ConfirmationResult,
    MultiConfirmationMonitor,
)

from .retry_handler import (
    RetryHandler,
    RetryConfig,
    RetryStrategy,
    ExponentialBackoff,
    CircuitBreaker,
    CircuitBreakerOpen,
    RetryExhausted,
    AdaptiveRetryHandler,
)

__all__ = [
    # Async executor
    "AsyncTradeExecutor",
    "ExecutionConfig",
    "ExecutionResult",
    "ExecutionStatus",
    "SubmitMode",
    # Transaction pool
    "TransactionPool",
    "PoolConfig",
    "PendingTransaction",
    "TransactionStatus",
    "PriorityCalculator",
    # Confirmation monitor
    "ConfirmationMonitor",
    "ConfirmationConfig",
    "ConfirmationStatus",
    "ConfirmationResult",
    "MultiConfirmationMonitor",
    # Retry handler
    "RetryHandler",
    "RetryConfig",
    "RetryStrategy",
    "ExponentialBackoff",
    "CircuitBreaker",
    "CircuitBreakerOpen",
    "RetryExhausted",
    "AdaptiveRetryHandler",
]
