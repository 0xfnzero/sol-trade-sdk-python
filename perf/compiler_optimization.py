"""
Compiler-level optimizations for Python code.

Provides JIT compilation hints, C extensions integration, and
performance-critical code paths.
"""

from __future__ import annotations

import functools
import inspect
import logging
import sys
import types
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


@dataclass
class JITConfig:
    """Configuration for JIT compilation."""
    enabled: bool = True
    cache_size: int = 128
    optimization_level: str = "O3"  # O0, O1, O2, O3
    inline_threshold: int = 1000
    loop_vectorize: bool = True
    slp_vectorize: bool = True  # Superword-level parallelism


class NumbaOptimizer:
    """
    Numba JIT optimizer wrapper.

    Provides JIT compilation for numerical Python code.
    """

    def __init__(self, config: Optional[JITConfig] = None):
        self.config = config or JITConfig()
        self._numba_available = False
        self._numba = None
        self._check_numba()

    def _check_numba(self) -> bool:
        """Check if Numba is available."""
        try:
            import numba
            self._numba = numba
            self._numba_available = True
            logger.info("Numba JIT compiler available")
            return True
        except ImportError:
            logger.info("Numba not available, JIT disabled")
            return False

    def is_available(self) -> bool:
        """Check if Numba is available."""
        return self._numba_available

    def jit(
        self,
        func: Optional[F] = None,
        *,
        nopython: bool = True,
        cache: bool = True,
        parallel: bool = False,
        fastmath: bool = True,
        **kwargs
    ) -> Union[F, Callable[[F], F]]:
        """
        JIT compile a function.

        Args:
            func: Function to compile
            nopython: Use nopython mode (no Python interpreter fallback)
            cache: Cache compiled code
            parallel: Enable automatic parallelization
            fastmath: Enable fast math optimizations

        Returns:
            JIT-compiled function or decorator
        """
        if not self._numba_available or not self.config.enabled:
            # Return original function if Numba not available
            if func is not None:
                return func
            return lambda f: f

        def decorator(f: F) -> F:
            return self._numba.jit(
                f,
                nopython=nopython,
                cache=cache,
                parallel=parallel,
                fastmath=fastmath,
                **kwargs
            )

        if func is not None:
            return decorator(func)
        return decorator

    def vectorize(
        self,
        signatures: Optional[List[str]] = None,
        target: str = "parallel",
        cache: bool = True
    ) -> Callable[[F], F]:
        """
        Create a Numba vectorized ufunc.

        Args:
            signatures: Type signatures (e.g., ["float64(float64)"])
            target: "cpu", "parallel", or "cuda"
            cache: Cache compiled code

        Returns:
            Vectorized function decorator
        """
        if not self._numba_available or not self.config.enabled:
            # Fallback to numpy vectorize
            try:
                import numpy as np
                return lambda f: np.vectorize(f)
            except ImportError:
                return lambda f: f

        def decorator(f: F) -> F:
            return self._numba.vectorize(signatures, target=target, cache=cache)(f)

        return decorator

    def guvectorize(
        self,
        signatures: List[str],
        layout: str,
        target: str = "parallel"
    ) -> Callable[[F], F]:
        """
        Generalized universal function with Numba.

        Args:
            signatures: Type signatures
            layout: Array dimension layout string
            target: Target backend

        Returns:
            GUVectorized function decorator
        """
        if not self._numba_available or not self.config.enabled:
            return lambda f: f

        def decorator(f: F) -> F:
            return self._numba.guvectorize(signatures, layout, target=target)(f)

        return decorator


class CythonOptimizer:
    """
    Cython integration for compiled extensions.

    Falls back to pure Python if Cython not available.
    """

    def __init__(self):
        self._cython_available = False
        self._check_cython()

    def _check_cython(self) -> bool:
        """Check if Cython is available."""
        try:
            import Cython
            self._cython_available = True
            logger.info("Cython available")
            return True
        except ImportError:
            logger.info("Cython not available")
            return False

    def is_available(self) -> bool:
        """Check if Cython is available."""
        return self._cython_available

    def compile_inline(
        self,
        code: str,
        language: str = "c",
        extra_compile_args: Optional[List[str]] = None
    ) -> Any:
        """
        Compile inline Cython/C code.

        Args:
            code: Source code to compile
            language: "c" or "c++"
            extra_compile_args: Additional compiler flags

        Returns:
            Compiled module
        """
        if not self._cython_available:
            raise ImportError("Cython not available for inline compilation")

        import Cython.Compiler.Errors
        from Cython.Build.Inline import cython_inline

        return cython_inline(
            code,
            language=language,
            extra_compile_args=extra_compile_args or []
        )


class InlineOptimizer:
    """Function inlining optimizer."""

    def __init__(self, threshold: int = 100):
        """
        Initialize inline optimizer.

        Args:
            threshold: Maximum bytecode size to inline
        """
        self.threshold = threshold

    def inline(self, func: F) -> F:
        """
        Mark function for inlining (manual optimization hint).

        In Python this doesn't auto-inline, but documents intent
        and may be used by future optimizers.
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        wrapper._inline_hint = True
        wrapper._original = func
        return wrapper

    def force_inline(self, func: F) -> str:
        """
        Create inlined version of function as source code.

        This is useful for hot loops where function call overhead matters.
        """
        source = inspect.getsource(func)
        # Remove function definition line
        lines = source.split('\n')
        while lines and not lines[0].strip().startswith('def '):
            lines.pop(0)
        if lines:
            lines.pop(0)  # Remove def line

        # Dedent
        min_indent = float('inf')
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                indent = len(line) - len(stripped)
                min_indent = min(min_indent, indent)

        if min_indent == float('inf'):
            min_indent = 0

        result = '\n'.join(line[min_indent:] for line in lines)
        return result


class LoopOptimizer:
    """Loop optimization utilities."""

    @staticmethod
    def unroll(
        func: F,
        unroll_factor: int = 4
    ) -> F:
        """
        Manual loop unrolling decorator.

        Note: This is a hint/documentation. For actual unrolling,
        use Numba or rewrite the loop manually.
        """
        func._unroll_hint = unroll_factor
        return func

    @staticmethod
    def vectorize_hint(func: F) -> F:
        """Mark function for vectorization."""
        func._vectorize_hint = True
        return func

    @staticmethod
    def parallel_hint(func: F) -> F:
        """Mark function for parallel execution."""
        func._parallel_hint = True
        return func


class CacheOptimizer:
    """Cache optimization utilities."""

    @staticmethod
    def cache_aligned_array(
        shape: Tuple[int, ...],
        dtype: str = "float64",
        align: int = 64
    ) -> Any:
        """
        Create cache-aligned array.

        Args:
            shape: Array shape
            dtype: Data type
            align: Byte alignment

        Returns:
            Aligned numpy array
        """
        try:
            import numpy as np

            # Calculate total size
            itemsize = np.dtype(dtype).itemsize
            total_size = 1
            for dim in shape:
                total_size *= dim

            # Allocate with padding for alignment
            nbytes = total_size * itemsize
            padded = nbytes + align

            # Create buffer
            buf = np.empty(padded, dtype=np.uint8)

            # Find aligned offset
            offset = align - (buf.ctypes.data % align)
            if offset == align:
                offset = 0

            # Create view at aligned position
            aligned = buf[offset:offset + nbytes].view(dtype)
            return aligned.reshape(shape)

        except ImportError:
            logger.warning("NumPy not available for aligned array")
            return None

    @staticmethod
    def prefetch_hint(address: int) -> None:
        """
        Software prefetch hint.

        Note: This is a no-op in pure Python but documents intent.
        """
        pass


class BranchOptimizer:
    """Branch prediction optimization hints."""

    @staticmethod
    def likely(condition: bool) -> bool:
        """Hint that condition is likely true."""
        return condition

    @staticmethod
    def unlikely(condition: bool) -> bool:
        """Hint that condition is likely false."""
        return condition

    @staticmethod
    def cold_path(func: F) -> F:
        """Mark function as cold path (rarely executed)."""
        func._cold_path = True
        return func

    @staticmethod
    def hot_path(func: F) -> F:
        """Mark function as hot path (frequently executed)."""
        func._hot_path = True
        return func


class ProfileGuidedOptimizer:
    """Profile-guided optimization utilities."""

    def __init__(self):
        self._profile_data: Dict[str, Dict[str, Any]] = {}
        self._call_counts: Dict[str, int] = {}

    def instrument(self, func: F) -> F:
        """Instrument function for profiling."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            name = func.__qualname__
            self._call_counts[name] = self._call_counts.get(name, 0) + 1

            import time
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - start

            if name not in self._profile_data:
                self._profile_data[name] = {
                    'calls': 0,
                    'total_time': 0.0,
                    'min_time': float('inf'),
                    'max_time': 0.0
                }

            data = self._profile_data[name]
            data['calls'] += 1
            data['total_time'] += elapsed
            data['min_time'] = min(data['min_time'], elapsed)
            data['max_time'] = max(data['max_time'], elapsed)

            return result

        return wrapper

    def get_hot_functions(self, top_n: int = 10) -> List[Tuple[str, int]]:
        """Get most frequently called functions."""
        sorted_funcs = sorted(
            self._call_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_funcs[:top_n]

    def get_slow_functions(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """Get functions with highest average execution time."""
        avg_times = []
        for name, data in self._profile_data.items():
            if data['calls'] > 0:
                avg = data['total_time'] / data['calls']
                avg_times.append((name, avg))

        sorted_funcs = sorted(avg_times, key=lambda x: x[1], reverse=True)
        return sorted_funcs[:top_n]


class OptimizedMath:
    """Optimized mathematical operations."""

    def __init__(self):
        self._numba = NumbaOptimizer()

    def fast_exp(self, x: float) -> float:
        """Fast exponential approximation."""
        # Cephes approximation
        if x < -708:
            return 0.0
        if x > 709:
            return float('inf')

        import math
        return math.exp(x)

    def fast_log(self, x: float) -> float:
        """Fast logarithm approximation."""
        import math
        return math.log(x)

    def fast_sqrt(self, x: float) -> float:
        """Fast square root."""
        import math
        return math.sqrt(x)

    def fast_pow(self, base: float, exp: float) -> float:
        """Fast power computation."""
        import math
        return math.pow(base, exp)

    def fast_inv_sqrt(self, x: float) -> float:
        """Fast inverse square root (Quake III algorithm)."""
        if x <= 0:
            return float('inf')

        import struct
        threehalfs = 1.5
        x2 = x * 0.5
        y = x

        # Evil floating point bit level hacking
        i = struct.unpack('I', struct.pack('f', y))[0]
        i = 0x5f3759df - (i >> 1)
        y = struct.unpack('f', struct.pack('I', i))[0]

        # Newton iteration
        y = y * (threehalfs - (x2 * y * y))

        return y


# Global optimizer instances
_numba_optimizer: Optional[NumbaOptimizer] = None
_profile_optimizer: Optional[ProfileGuidedOptimizer] = None


def get_numba_optimizer(config: Optional[JITConfig] = None) -> NumbaOptimizer:
    """Get or create global Numba optimizer."""
    global _numba_optimizer
    if _numba_optimizer is None:
        _numba_optimizer = NumbaOptimizer(config)
    return _numba_optimizer


def get_profile_optimizer() -> ProfileGuidedOptimizer:
    """Get or create global profile optimizer."""
    global _profile_optimizer
    if _profile_optimizer is None:
        _profile_optimizer = ProfileGuidedOptimizer()
    return _profile_optimizer


# Convenience decorators
def jit(**kwargs) -> Callable[[F], F]:
    """JIT decorator using global Numba optimizer."""
    optimizer = get_numba_optimizer()
    return optimizer.jit(**kwargs)


def vectorize(signatures=None, **kwargs) -> Callable[[F], F]:
    """Vectorize decorator using global Numba optimizer."""
    optimizer = get_numba_optimizer()
    return optimizer.vectorize(signatures, **kwargs)


def profile(func: F) -> F:
    """Profile decorator using global profile optimizer."""
    optimizer = get_profile_optimizer()
    return optimizer.instrument(func)
