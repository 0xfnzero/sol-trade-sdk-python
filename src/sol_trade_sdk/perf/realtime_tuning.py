"""
Real-time tuning for consistent low latency.

Provides:
- Real-time scheduling policies
- Thread priority management
- Process niceness adjustment
"""

import os
import sys
import threading
from enum import IntEnum
from typing import Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ThreadPriority(IntEnum):
    """Thread priority levels."""
    IDLE = 0
    LOWEST = 1
    LOW = 2
    NORMAL = 3
    HIGH = 4
    HIGHEST = 5
    REALTIME = 6


@dataclass
class RealtimeConfig:
    """Configuration for real-time tuning."""
    enable_realtime_scheduling: bool = True
    thread_priority: ThreadPriority = ThreadPriority.HIGH
    enable_nice_adjustment: bool = True
    nice_value: int = -10  # Higher priority (lower nice value)
    enable_irq_affinity: bool = False  # Requires root
    disable_cpu_freq_scaling: bool = False  # Requires root


class RealtimeTuner:
    """
    Real-time performance tuner.

    Adjusts system settings for consistent low latency.
    """

    def __init__(self, config: Optional[RealtimeConfig] = None):
        self.config = config or RealtimeConfig()
        self._original_nice: Optional[int] = None
        self._applied = False

    def apply(self) -> bool:
        """Apply real-time tuning settings."""
        if self._applied:
            return True

        success = True

        # Adjust process nice value
        if self.config.enable_nice_adjustment:
            if not self._set_nice(self.config.nice_value):
                success = False

        # Set real-time scheduling
        if self.config.enable_realtime_scheduling:
            if not self._set_realtime_scheduling():
                success = False

        self._applied = success
        return success

    def _set_nice(self, nice_value: int) -> bool:
        """
        Set process nice value.

        Args:
            nice_value: -20 (highest priority) to 19 (lowest priority)

        Returns:
            True if successful
        """
        try:
            self._original_nice = os.nice(0)
            os.nice(nice_value - self._original_nice)
            logger.info(f"Process nice value set to {nice_value}")
            return True
        except PermissionError:
            logger.warning("Cannot adjust nice value (requires root/capabilities)")
            return False
        except Exception as e:
            logger.error(f"Failed to set nice value: {e}")
            return False

    def _set_realtime_scheduling(self) -> bool:
        """
        Set real-time scheduling policy.

        Note: Requires root or CAP_SYS_NICE capability.
        """
        if sys.platform == "linux":
            try:
                import ctypes
                libc = ctypes.CDLL("libc.so.6")

                # SCHED_FIFO = 1, SCHED_RR = 2
                SCHED_FIFO = 1
                SCHED_RR = 2

                # Set scheduling policy
                param = ctypes.c_int(99)  # Max priority for FIFO
                result = libc.sched_setscheduler(0, SCHED_FIFO, ctypes.byref(param))

                if result == 0:
                    logger.info("Real-time scheduling (SCHED_FIFO) enabled")
                    return True
                else:
                    logger.warning("Failed to set real-time scheduling (requires root)")
                    return False

            except Exception as e:
                logger.error(f"Error setting real-time scheduling: {e}")
                return False

        else:
            logger.warning(f"Real-time scheduling not supported on {sys.platform}")
            return False

    def set_thread_priority(self, priority: ThreadPriority) -> bool:
        """
        Set priority for current thread.

        Args:
            priority: ThreadPriority level

        Returns:
            True if successful
        """
        if sys.platform == "linux":
            return self._set_linux_thread_priority(priority)
        elif sys.platform == "win32":
            return self._set_windows_thread_priority(priority)
        else:
            logger.warning(f"Thread priority not supported on {sys.platform}")
            return False

    def _set_linux_thread_priority(self, priority: ThreadPriority) -> bool:
        """Set thread priority on Linux."""
        try:
            # Map our priority levels to nice values
            nice_map = {
                ThreadPriority.IDLE: 19,
                ThreadPriority.LOWEST: 10,
                ThreadPriority.LOW: 5,
                ThreadPriority.NORMAL: 0,
                ThreadPriority.HIGH: -5,
                ThreadPriority.HIGHEST: -10,
                ThreadPriority.REALTIME: -20,
            }

            nice_value = nice_map.get(priority, 0)

            # Get current thread ID
            tid = threading.current_thread().ident

            # Set priority using setpriority
            import ctypes
            libc = ctypes.CDLL("libc.so.6")
            PRIO_PROCESS = 0

            result = libc.setpriority(PRIO_PROCESS, tid, nice_value)

            if result == 0:
                logger.debug(f"Thread priority set to {priority.name}")
                return True
            else:
                logger.warning(f"Failed to set thread priority (errno: {ctypes.get_errno()})")
                return False

        except Exception as e:
            logger.error(f"Error setting thread priority: {e}")
            return False

    def _set_windows_thread_priority(self, priority: ThreadPriority) -> bool:
        """Set thread priority on Windows."""
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32

            # Map priority levels to Windows constants
            priority_map = {
                ThreadPriority.IDLE: -15,      # THREAD_PRIORITY_IDLE
                ThreadPriority.LOWEST: -2,     # THREAD_PRIORITY_LOWEST
                ThreadPriority.LOW: -1,        # THREAD_PRIORITY_BELOW_NORMAL
                ThreadPriority.NORMAL: 0,      # THREAD_PRIORITY_NORMAL
                ThreadPriority.HIGH: 1,        # THREAD_PRIORITY_ABOVE_NORMAL
                ThreadPriority.HIGHEST: 2,     # THREAD_PRIORITY_HIGHEST
                ThreadPriority.REALTIME: 15,   # THREAD_PRIORITY_TIME_CRITICAL
            }

            win_priority = priority_map.get(priority, 0)

            # Get current thread handle
            handle = kernel32.GetCurrentThread()

            result = kernel32.SetThreadPriority(handle, win_priority)

            if result:
                logger.debug(f"Thread priority set to {priority.name}")
                return True
            else:
                logger.warning("Failed to set Windows thread priority")
                return False

        except Exception as e:
            logger.error(f"Error setting Windows thread priority: {e}")
            return False

    def reset(self) -> None:
        """Reset all tuning to default values."""
        if self._original_nice is not None:
            try:
                current = os.nice(0)
                os.nice(self._original_nice - current)
                logger.info(f"Nice value reset to {self._original_nice}")
            except Exception as e:
                logger.error(f"Failed to reset nice value: {e}")

        self._applied = False


class ThreadPriorityManager:
    """Manages thread priorities across the application."""

    def __init__(self):
        self._thread_priorities: Dict[int, ThreadPriority] = {}
        self._tuner = RealtimeTuner()

    def set_priority(self, thread: Optional[threading.Thread] = None, priority: ThreadPriority = ThreadPriority.NORMAL) -> bool:
        """
        Set priority for a thread.

        Args:
            thread: Thread to set priority for (default: current thread)
            priority: Priority level

        Returns:
            True if successful
        """
        if thread is None:
            thread = threading.current_thread()

        self._thread_priorities[thread.ident] = priority
        return self._tuner.set_thread_priority(priority)

    def set_worker_priority(self) -> bool:
        """Set priority for worker threads."""
        return self.set_priority(priority=ThreadPriority.HIGH)

    def set_network_priority(self) -> bool:
        """Set priority for network I/O threads."""
        return self.set_priority(priority=ThreadPriority.HIGHEST)

    def set_timer_priority(self) -> bool:
        """Set priority for timer/scheduler threads."""
        return self.set_priority(priority=ThreadPriority.REALTIME)


# Global tuner instance
_global_tuner: Optional[RealtimeTuner] = None


def get_realtime_tuner(config: Optional[RealtimeConfig] = None) -> RealtimeTuner:
    """Get or create global real-time tuner."""
    global _global_tuner
    if _global_tuner is None:
        _global_tuner = RealtimeTuner(config)
    return _global_tuner
