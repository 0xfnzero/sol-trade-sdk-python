"""
Hardware-level optimizations for CPU and memory.

Provides:
- CPU affinity and pinning
- NUMA-aware memory allocation
- Cache optimization
"""

import os
import sys
import platform
from typing import Optional, List, Dict, Set
from dataclasses import dataclass
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class CPUAffinity:
    """CPU affinity configuration."""
    cores: List[int]
    strict: bool = True  # Fail if can't set affinity


class CPUAffinityManager:
    """Manages CPU affinity for threads and processes."""

    def __init__(self):
        self._original_affinity: Optional[Set[int]] = None
        self._current_affinity: Optional[Set[int]] = None

    def get_available_cores(self) -> int:
        """Get number of available CPU cores."""
        return os.cpu_count() or 4

    def get_current_affinity(self) -> Optional[Set[int]]:
        """Get current CPU affinity."""
        if sys.platform == "win32":
            return None  # Windows not supported

        try:
            import psutil
            process = psutil.Process()
            return set(process.cpu_affinity())
        except Exception as e:
            logger.warning(f"Failed to get CPU affinity: {e}")
            return None

    def set_affinity(self, cores: List[int]) -> bool:
        """
        Set CPU affinity for current process.

        Args:
            cores: List of CPU cores to pin to

        Returns:
            True if successful, False otherwise
        """
        if sys.platform == "win32":
            logger.warning("CPU affinity not supported on Windows")
            return False

        try:
            import psutil

            # Save original affinity
            if self._original_affinity is None:
                self._original_affinity = self.get_current_affinity()

            process = psutil.Process()
            process.cpu_affinity(cores)
            self._current_affinity = set(cores)

            logger.info(f"CPU affinity set to cores: {cores}")
            return True

        except Exception as e:
            logger.error(f"Failed to set CPU affinity: {e}")
            return False

    def set_thread_affinity(self, thread_id: int, cores: List[int]) -> bool:
        """
        Set CPU affinity for a specific thread.

        Note: This is platform-specific and may not work on all systems.
        """
        if sys.platform == "linux":
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6")

                # Create cpu_set_t
                cpu_set_size = 128  # Usually enough for 1024 CPUs
                cpu_set = ctypes.create_string_buffer(cpu_set_size)

                # Set bits for specified cores
                for core in cores:
                    cpu_set[core // 8] = chr(ord(cpu_set[core // 8]) | (1 << (core % 8)))

                # Call pthread_setaffinity_np
                result = libc.pthread_setaffinity_np(
                    thread_id,
                    cpu_set_size,
                    ctypes.cast(cpu_set, ctypes.c_void_p)
                )

                if result == 0:
                    logger.info(f"Thread {thread_id} affinity set to cores: {cores}")
                    return True
                else:
                    logger.error(f"pthread_setaffinity_np failed with code: {result}")
                    return False

            except Exception as e:
                logger.error(f"Failed to set thread affinity: {e}")
                return False

        else:
            logger.warning(f"Thread-level CPU affinity not supported on {sys.platform}")
            return False

    def reset_affinity(self) -> bool:
        """Reset CPU affinity to original value."""
        if self._original_affinity is None:
            return True

        return self.set_affinity(list(self._original_affinity))


class CacheOptimizer:
    """
    CPU cache optimization utilities.

    Provides cache-line alignment and prefetch hints.
    """

    CACHE_LINE_SIZE = 64  # Most modern CPUs have 64-byte cache lines
    L1_CACHE_SIZE = 32 * 1024  # 32KB typical L1
    L2_CACHE_SIZE = 256 * 1024  # 256KB typical L2
    L3_CACHE_SIZE = 8 * 1024 * 1024  # 8MB typical L3

    @staticmethod
    def align_to_cache_line(size: int) -> int:
        """Round up size to cache line boundary."""
        return (size + CacheOptimizer.CACHE_LINE_SIZE - 1) // CacheOptimizer.CACHE_LINE_SIZE * CacheOptimizer.CACHE_LINE_SIZE

    @staticmethod
    def get_cache_line_aligned_buffer(size: int) -> bytearray:
        """Create a buffer aligned to cache line boundary."""
        aligned_size = CacheOptimizer.align_to_cache_line(size)
        return bytearray(aligned_size)

    @staticmethod
    def prefetch_l1(address: int) -> None:
        """
        Prefetch data into L1 cache.

        Note: This requires platform-specific implementations.
        In pure Python, this is a no-op placeholder.
        """
        pass

    @staticmethod
    def prefetch_l2(address: int) -> None:
        """Prefetch data into L2 cache."""
        pass

    @staticmethod
    def prefetch_l3(address: int) -> None:
        """Prefetch data into L3 cache."""
        pass

    @staticmethod
    def optimize_data_structure_layout(fields: List[tuple]) -> List[tuple]:
        """
        Reorder fields to minimize cache line usage.

        Args:
            fields: List of (name, size) tuples

        Returns:
            Reordered list optimized for cache
        """
        # Sort by size descending to pack efficiently
        return sorted(fields, key=lambda x: x[1], reverse=True)


class NUMAOptimizer:
    """
    NUMA-aware memory optimization.

    Note: NUMA support requires platform-specific libraries.
    This is a placeholder for future implementation.
    """

    def __init__(self):
        self.numa_available = self._check_numa_support()

    def _check_numa_support(self) -> bool:
        """Check if NUMA is available on this system."""
        if sys.platform != "linux":
            return False

        try:
            # Check for NUMA support
            return os.path.exists("/sys/devices/system/node")
        except:
            return False

    def get_numa_nodes(self) -> int:
        """Get number of NUMA nodes."""
        if not self.numa_available:
            return 1

        try:
            import subprocess
            result = subprocess.run(
                ["numactl", "--hardware"],
                capture_output=True,
                text=True
            )
            # Parse output to count nodes
            return 1  # Simplified
        except:
            return 1

    def allocate_on_node(self, size: int, node: int) -> Optional[bytearray]:
        """
        Allocate memory on specific NUMA node.

        Note: Requires libnuma or similar.
        """
        if not self.numa_available:
            return bytearray(size)

        # Placeholder for NUMA-aware allocation
        return bytearray(size)


class HardwareOptimizer:
    """
    Main hardware optimization manager.

    Coordinates CPU affinity, cache optimization, and NUMA.
    """

    def __init__(self):
        self.cpu_manager = CPUAffinityManager()
        self.cache_optimizer = CacheOptimizer()
        self.numa_optimizer = NUMAOptimizer()
        self._initialized = False

    def initialize(self, cpu_cores: Optional[List[int]] = None) -> None:
        """Initialize hardware optimizations."""
        if self._initialized:
            return

        logger.info("Initializing HardwareOptimizer...")

        # Set CPU affinity
        if cpu_cores:
            self.cpu_manager.set_affinity(cpu_cores)
        else:
            # Use isolated cores if available
            isolated = self._get_isolated_cores()
            if isolated:
                self.cpu_manager.set_affinity(isolated)

        self._initialized = True
        logger.info("HardwareOptimizer initialized")

    def _get_isolated_cores(self) -> Optional[List[int]]:
        """Get isolated CPU cores from system configuration."""
        if sys.platform != "linux":
            return None

        try:
            with open("/sys/devices/system/cpu/isolated", "r") as f:
                content = f.read().strip()
                if content:
                    # Parse range format like "2-3,6-7"
                    cores = []
                    for part in content.split(","):
                        if "-" in part:
                            start, end = part.split("-")
                            cores.extend(range(int(start), int(end) + 1))
                        else:
                            cores.append(int(part))
                    return cores
        except:
            pass

        return None

    def get_optimal_thread_count(self) -> int:
        """Get optimal number of threads based on hardware."""
        cpu_count = os.cpu_count() or 4

        # Leave one core for system
        return max(1, cpu_count - 1)

    def shutdown(self) -> None:
        """Shutdown and reset hardware settings."""
        self.cpu_manager.reset_affinity()
        logger.info("HardwareOptimizer shutdown")


# Global instance
_global_hardware_optimizer: Optional[HardwareOptimizer] = None


def get_hardware_optimizer() -> HardwareOptimizer:
    """Get or create global hardware optimizer."""
    global _global_hardware_optimizer
    if _global_hardware_optimizer is None:
        _global_hardware_optimizer = HardwareOptimizer()
    return _global_hardware_optimizer
