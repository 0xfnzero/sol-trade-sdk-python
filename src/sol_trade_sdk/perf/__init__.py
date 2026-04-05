"""
Performance optimization modules for Sol Trade SDK.

This package provides various performance optimizations for ultra-low latency trading:
- Syscall bypass and batching
- Hardware optimizations (CPU affinity, NUMA)
- Zero-copy I/O
- SIMD vectorization
- Real-time tuning
- Kernel bypass (io_uring)
- Compiler optimizations (JIT, inlining)
- Protocol optimizations (transaction building, RPC)
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

from .simd import (
    SIMDConfig,
    SIMDDetector,
    SIMDProcessor,
    VectorizedMath,
    CryptoSIMD,
    AlignedArray,
    get_simd_processor,
)

from .kernel_bypass import (
    IOUringConfig,
    KernelBypassManager,
    DirectIOFile,
    AsyncSocket,
    MemoryMappedFile,
    IOBatchProcessor,
    get_kernel_bypass_manager,
)

from .compiler_optimization import (
    JITConfig,
    NumbaOptimizer,
    CythonOptimizer,
    InlineOptimizer,
    LoopOptimizer,
    CacheOptimizer,
    BranchOptimizer,
    ProfileGuidedOptimizer,
    OptimizedMath,
    jit,
    vectorize,
    profile,
)

from .protocol_optimization import (
    TransactionConfig,
    OptimizedInstruction,
    OptimizedTransaction,
    TransactionBuilder,
    RPCOptimizer,
    ComputeBudgetOptimizer,
    SerializationOptimizer,
    NetworkOptimizer,
    HotPathOptimizer,
    get_transaction_builder,
    get_rpc_optimizer,
    get_network_optimizer,
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
    # SIMD
    "SIMDConfig",
    "SIMDDetector",
    "SIMDProcessor",
    "VectorizedMath",
    "CryptoSIMD",
    "AlignedArray",
    "get_simd_processor",
    # Kernel bypass
    "IOUringConfig",
    "KernelBypassManager",
    "DirectIOFile",
    "AsyncSocket",
    "MemoryMappedFile",
    "IOBatchProcessor",
    "get_kernel_bypass_manager",
    # Compiler optimization
    "JITConfig",
    "NumbaOptimizer",
    "CythonOptimizer",
    "InlineOptimizer",
    "LoopOptimizer",
    "CacheOptimizer",
    "BranchOptimizer",
    "ProfileGuidedOptimizer",
    "OptimizedMath",
    "jit",
    "vectorize",
    "profile",
    # Protocol optimization
    "TransactionConfig",
    "OptimizedInstruction",
    "OptimizedTransaction",
    "TransactionBuilder",
    "RPCOptimizer",
    "ComputeBudgetOptimizer",
    "SerializationOptimizer",
    "NetworkOptimizer",
    "HotPathOptimizer",
    "get_transaction_builder",
    "get_rpc_optimizer",
    "get_network_optimizer",
]
