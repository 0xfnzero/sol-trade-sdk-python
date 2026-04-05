"""
Hot Path Module for Sol Trade SDK

Provides optimized trading execution with ZERO RPC calls in the hot path.
All data is prefetched before trading to minimize latency.

Key Components:
- HotPathState: Manages prefetched blockchain state
- HotPathExecutor: Executes trades using cached data only
- TradingContext: Context object for a single trade with all required data
"""

from .state import (
    HotPathConfig,
    HotPathState,
    PrefetchedData,
    AccountState,
    PoolState,
    TradingContext,
    HotPathError,
    StaleBlockhashError,
    MissingAccountError,
    ContextExpiredError,
)

from .executor import (
    HotPathExecutor,
    HotPathMetrics,
    TransactionBuilder,
    ExecuteOptions,
    ExecuteResult,
    create_hot_path_executor,
)

__all__ = [
    # State management
    'HotPathConfig',
    'HotPathState',
    'PrefetchedData',
    'AccountState',
    'PoolState',
    'TradingContext',
    
    # Errors
    'HotPathError',
    'StaleBlockhashError',
    'MissingAccountError',
    'ContextExpiredError',
    
    # Execution
    'HotPathExecutor',
    'HotPathMetrics',
    'TransactionBuilder',
    'ExecuteOptions',
    'ExecuteResult',
    'create_hot_path_executor',
]
