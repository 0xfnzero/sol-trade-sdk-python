"""
Performance optimization modules for Sol Trade SDK.

This package provides various performance optimizations for ultra-low latency trading:
- Syscall bypass and batching
- Hardware optimizations (CPU affinity, NUMA)
- Zero-copy I/O
- SIMD vectorization
- Real-time tuning
- Kernel bypass (io_uring)
"""

from .syscall_bypass import (
    SyscallBypassConfig,
    SyscallBypassManager,
    SyscallRequest,
    FastTimeProvider,
)

from .ultra_low_latency import (
    UltraLowLatencyConfig,
    LatencyOptimizer,
    LatencyMetrics,
)

from .zero_copy_io import (
    ZeroCopyBuffer,
    BufferPool,
    ZeroCopySerializer,
)

from .hardware_optimizations import (
    HardwareOptimizer,
    CPUAffinity,
    CacheOptimizer,
)

from .realtime_tuning import (
    RealtimeTuner,
    RealtimeConfig,
    ThreadPriority,
)

__all__ = [
    # Syscall bypass
    "SyscallBypassConfig",
    "SyscallBypassManager",
    "SyscallRequest",
    "FastTimeProvider",
    # Ultra low latency
    "UltraLowLatencyConfig",
    "LatencyOptimizer",
    "LatencyMetrics",
    # Zero copy I/O
    "ZeroCopyBuffer",
    "BufferPool",
    "ZeroCopySerializer",
    # Hardware optimizations
    "HardwareOptimizer",
    "CPUAffinity",
    "CacheOptimizer",
    # Realtime tuning
    "RealtimeTuner",
    "RealtimeConfig",
    "ThreadPriority",
]
