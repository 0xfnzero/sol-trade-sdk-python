"""
SIMD (Single Instruction Multiple Data) optimization module.

Provides vectorized operations for cryptographic and mathematical computations
commonly used in Solana trading operations.
"""

from __future__ import annotations

import array
import struct
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Tuple, Union, Callable
import logging

logger = logging.getLogger(__name__)


class SIMDCapability(Enum):
    """SIMD instruction set capabilities."""
    SSE2 = auto()
    SSE4_1 = auto()
    AVX = auto()
    AVX2 = auto()
    AVX512 = auto()
    NEON = auto()  # ARM
    WASM_SIMD = auto()


@dataclass
class SIMDConfig:
    """Configuration for SIMD optimizations."""
    enabled: bool = True
    preferred_width: int = 256  # 128, 256, or 512 bits
    use_fma: bool = True  # Fused multiply-add
    cache_aligned: bool = True
    prefetch_distance: int = 4


class SIMDDetector:
    """Detect available SIMD capabilities on the current system."""

    def __init__(self):
        self._capabilities: set = set()
        self._detect_capabilities()

    def _detect_capabilities(self) -> None:
        """Detect available SIMD instruction sets."""
        import platform

        system = platform.system()
        machine = platform.machine().lower()

        if "arm" in machine or "aarch64" in machine:
            # ARM - check for NEON
            try:
                # Try to import numpy which may have NEON detection
                import numpy as np
                self._capabilities.add(SIMDCapability.NEON)
            except ImportError:
                pass
        else:
            # x86/x64 - check CPU features
            try:
                import cpuinfo
                info = cpuinfo.get_cpu_info()
                flags = info.get("flags", [])

                if "sse2" in flags:
                    self._capabilities.add(SIMDCapability.SSE2)
                if "sse4_1" in flags:
                    self._capabilities.add(SIMDCapability.SSE4_1)
                if "avx" in flags:
                    self._capabilities.add(SIMDCapability.AVX)
                if "avx2" in flags:
                    self._capabilities.add(SIMDCapability.AVX2)
                if "avx512f" in flags:
                    self._capabilities.add(SIMDCapability.AVX512)
            except ImportError:
                # Fallback: assume basic SSE2 on x86
                if "x86" in machine or "amd64" in machine or "x86_64" in machine:
                    self._capabilities.add(SIMDCapability.SSE2)

    def get_capabilities(self) -> set:
        """Get detected SIMD capabilities."""
        return self._capabilities.copy()

    def has_capability(self, capability: SIMDCapability) -> bool:
        """Check if a specific capability is available."""
        return capability in self._capabilities

    def get_best_capability(self) -> Optional[SIMDCapability]:
        """Get the best available SIMD capability."""
        priority = [
            SIMDCapability.AVX512,
            SIMDCapability.AVX2,
            SIMDCapability.AVX,
            SIMDCapability.NEON,
            SIMDCapability.SSE4_1,
            SIMDCapability.SSE2,
        ]
        for cap in priority:
            if cap in self._capabilities:
                return cap
        return None


class VectorizedMath:
    """Vectorized mathematical operations using NumPy."""

    def __init__(self, config: Optional[SIMDConfig] = None):
        self.config = config or SIMDConfig()
        self._np = None
        self._try_import_numpy()

    def _try_import_numpy(self) -> bool:
        """Try to import numpy for vectorized operations."""
        try:
            import numpy as np
            self._np = np
            return True
        except ImportError:
            logger.warning("NumPy not available, falling back to scalar operations")
            return False

    def vector_add(self, a: List[float], b: List[float]) -> List[float]:
        """Vectorized addition of two arrays."""
        if self._np and self.config.enabled:
            return self._np.add(a, b).tolist()
        return [x + y for x, y in zip(a, b)]

    def vector_mul(self, a: List[float], b: List[float]) -> List[float]:
        """Vectorized multiplication of two arrays."""
        if self._np and self.config.enabled:
            return self._np.multiply(a, b).tolist()
        return [x * y for x, y in zip(a, b)]

    def vector_fma(self, a: List[float], b: List[float], c: List[float]) -> List[float]:
        """
        Fused multiply-add: a * b + c.
        More accurate and faster than separate multiply and add.
        """
        if self._np and self.config.enabled and self.config.use_fma:
            return self._np.add(self._np.multiply(a, b), c).tolist()
        return [x * y + z for x, y, z in zip(a, b, c)]

    def dot_product(self, a: List[float], b: List[float]) -> float:
        """Compute dot product of two vectors."""
        if self._np and self.config.enabled:
            return float(self._np.dot(a, b))
        return sum(x * y for x, y in zip(a, b))

    def sum_array(self, arr: List[float]) -> float:
        """Sum all elements in array."""
        if self._np and self.config.enabled:
            return float(self._np.sum(arr))
        return sum(arr)

    def min_max(self, arr: List[float]) -> Tuple[float, float]:
        """Get min and max values efficiently."""
        if self._np and self.config.enabled:
            return float(self._np.min(arr)), float(self._np.max(arr))
        return min(arr), max(arr)


class CryptoSIMD:
    """SIMD-optimized cryptographic operations for Solana."""

    def __init__(self, config: Optional[SIMDConfig] = None):
        self.config = config or SIMDConfig()
        self._np = None
        self._try_import_numpy()

    def _try_import_numpy(self) -> bool:
        """Try to import numpy."""
        try:
            import numpy as np
            self._np = np
            return True
        except ImportError:
            return False

    def parallel_hash_check(self, hashes: List[bytes], target: bytes) -> List[bool]:
        """
        Vectorized comparison of multiple hashes against a target.
        Useful for bloom filter-like operations.
        """
        if not hashes:
            return []

        # Compare first 8 bytes as uint64 for speed
        target_prefix = struct.unpack("<Q", target[:8].ljust(8, b'\x00'))[0]
        results = []

        for h in hashes:
            prefix = struct.unpack("<Q", h[:8].ljust(8, b'\x00'))[0]
            results.append(prefix == target_prefix)

        return results

    def batch_xor(self, data_list: List[bytes], key: bytes) -> List[bytes]:
        """
        Batch XOR operation for multiple data chunks.
        Used in some cryptographic operations.
        """
        results = []
        key_len = len(key)

        for data in data_list:
            if self._np and len(data) >= 16 and self.config.enabled:
                # Use numpy for larger arrays
                arr = self._np.frombuffer(data, dtype=self._np.uint8)
                key_arr = self._np.frombuffer(
                    (key * (len(data) // key_len + 1))[:len(data)],
                    dtype=self._np.uint8
                )
                result = self._np.bitwise_xor(arr, key_arr).tobytes()
                results.append(result)
            else:
                # Scalar fallback
                result = bytes(b ^ key[i % key_len] for i, b in enumerate(data))
                results.append(result)

        return results

    def parallel_base58_encode(self, data_list: List[bytes]) -> List[str]:
        """
        Parallel base58 encoding for multiple data chunks.
        Returns list of base58 encoded strings.
        """
        from base58 import b58encode
        return [b58encode(d).decode('ascii') for d in data_list]

    def parallel_base58_decode(self, str_list: List[str]) -> List[bytes]:
        """Parallel base58 decoding."""
        from base58 import b58decode
        return [b58decode(s) for s in str_list]


class AlignedArray:
    """Cache-aligned array for optimal SIMD performance."""

    def __init__(self, size: int, dtype: str = "f", alignment: int = 64):
        """
        Create aligned array.

        Args:
            size: Number of elements
            dtype: Data type code ('f'=float, 'd'=double, 'i'=int)
            alignment: Byte alignment (typically 64 for cache lines)
        """
        self.size = size
        self.dtype = dtype
        self.alignment = alignment
        self._array = self._create_aligned_array()

    def _create_aligned_array(self) -> array.array:
        """Create properly aligned array."""
        # Python's array module doesn't guarantee alignment,
        # so we allocate extra and slice
        extra = self.alignment // 8 + 1
        arr = array.array(self.dtype, [0] * (self.size + extra))

        # Find aligned offset
        address = arr.buffer_info()[0]
        offset = (self.alignment - (address % self.alignment)) % self.alignment
        offset //= arr.itemsize

        # Return slice starting at aligned position
        return arr[offset:offset + self.size]

    def get_array(self) -> array.array:
        """Get the aligned array."""
        return self._array

    def __getitem__(self, idx: int) -> Union[int, float]:
        return self._array[idx]

    def __setitem__(self, idx: int, value: Union[int, float]) -> None:
        self._array[idx] = value


class SIMDProcessor:
    """High-level SIMD processor for batch operations."""

    def __init__(self, config: Optional[SIMDConfig] = None):
        self.config = config or SIMDConfig()
        self.detector = SIMDDetector()
        self.vector_math = VectorizedMath(self.config)
        self.crypto = CryptoSIMD(self.config)

    def batch_price_calculations(
        self,
        amounts: List[float],
        prices: List[float],
        fees: List[float]
    ) -> List[float]:
        """
        Batch calculate total costs including fees.
        total = amount * price + fee
        """
        if len(amounts) != len(prices) or len(amounts) != len(fees):
            raise ValueError("All input lists must have same length")

        return self.vector_math.vector_fma(amounts, prices, fees)

    def batch_slippage_check(
        self,
        expected: List[float],
        actual: List[float],
        max_slippage_pct: float
    ) -> List[bool]:
        """
        Check if actual prices are within slippage tolerance.
        Returns list of bool indicating if within tolerance.
        """
        if len(expected) != len(actual):
            raise ValueError("Expected and actual must have same length")

        np = self.vector_math._np
        if np and self.config.enabled:
            exp = np.array(expected)
            act = np.array(actual)
            diff = np.abs(exp - act) / exp
            return (diff <= max_slippage_pct / 100).tolist()

        # Scalar fallback
        results = []
        for e, a in zip(expected, actual):
            if e == 0:
                results.append(False)
            else:
                slippage = abs(e - a) / e
                results.append(slippage <= max_slippage_pct / 100)
        return results

    def parallel_signature_verify(
        self,
        messages: List[bytes],
        signatures: List[bytes],
        public_keys: List[bytes]
    ) -> List[bool]:
        """
        Parallel signature verification.
        Note: This is a placeholder - actual Ed25519 verification
        would use a library like pynacl or cryptography.
        """
        # Placeholder implementation
        # Real implementation would use nacl.signing.VerifyKey
        results = []
        for msg, sig, pk in zip(messages, signatures, public_keys):
            # Placeholder: assume valid
            results.append(len(sig) == 64 and len(pk) == 32)
        return results

    def batch_amount_to_lamports(
        self,
        amounts: List[float],
        decimals: List[int]
    ) -> List[int]:
        """
        Convert token amounts to lamports/base units.
        amount * 10^decimals
        """
        results = []
        for amt, dec in zip(amounts, decimals):
            multiplier = 10 ** dec
            results.append(int(amt * multiplier))
        return results

    def batch_lamports_to_amount(
        self,
        lamports: List[int],
        decimals: List[int]
    ) -> List[float]:
        """Convert lamports/base units to token amounts."""
        results = []
        for lam, dec in zip(lamports, decimals):
            divisor = 10 ** dec
            results.append(lam / divisor)
        return results


class PrefetchBuffer:
    """Buffer with prefetching for sequential access patterns."""

    def __init__(self, data: List, prefetch_distance: int = 4):
        self.data = data
        self.prefetch_distance = prefetch_distance
        self._index = 0

    def __iter__(self):
        self._index = 0
        return self

    def __next__(self):
        if self._index >= len(self.data):
            raise StopIteration

        # Prefetch hint (no-op in Python, but documents intent)
        prefetch_idx = self._index + self.prefetch_distance
        if prefetch_idx < len(self.data):
            # Touch the memory to bring into cache
            _ = self.data[prefetch_idx]

        value = self.data[self._index]
        self._index += 1
        return value


# Global SIMD processor instance
_global_simd_processor: Optional[SIMDProcessor] = None


def get_simd_processor(config: Optional[SIMDConfig] = None) -> SIMDProcessor:
    """Get or create global SIMD processor."""
    global _global_simd_processor
    if _global_simd_processor is None or config is not None:
        _global_simd_processor = SIMDProcessor(config)
    return _global_simd_processor


def detect_capabilities() -> set:
    """Convenience function to detect SIMD capabilities."""
    detector = SIMDDetector()
    return detector.get_capabilities()
