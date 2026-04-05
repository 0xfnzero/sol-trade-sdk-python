"""
High-performance clock implementation.

Uses monotonic clock + base UTC timestamp to avoid frequent syscalls.
Aligned with sol-parser-sdk for consistent timing measurements.
"""

import time
from typing import Optional
from dataclasses import dataclass, field


@dataclass
class HighPerformanceClock:
    """High-performance clock: monotonic + base UTC microsecond timestamp."""

    base_monotonic: float = field(default_factory=time.monotonic)
    base_timestamp_us: int = field(default_factory=lambda: int(time.time() * 1_000_000))
    last_calibration: float = field(default_factory=time.monotonic)
    calibration_interval_secs: int = 300  # 5 minutes

    def __post_init__(self):
        """Calibrate on initialization for accuracy."""
        self._calibrate()

    def _calibrate(self) -> None:
        """Sample multiple times and use the lowest-latency baseline."""
        best_offset = float('inf')
        best_monotonic = 0.0
        best_timestamp = 0

        for _ in range(3):
            monotonic_before = time.monotonic()
            timestamp = int(time.time() * 1_000_000)
            monotonic_after = time.monotonic()
            sample_latency = (monotonic_after - monotonic_before) * 1_000_000_000  # nanoseconds

            if sample_latency < best_offset:
                best_offset = sample_latency
                best_monotonic = monotonic_before
                best_timestamp = timestamp

        self.base_monotonic = best_monotonic
        self.base_timestamp_us = best_timestamp
        self.last_calibration = time.monotonic()

    def now_micros(self) -> int:
        """Get current time in microseconds (UTC scale)."""
        elapsed = time.monotonic() - self.base_monotonic
        return self.base_timestamp_us + int(elapsed * 1_000_000)

    def now_micros_with_calibration(self) -> int:
        """Get current time with automatic recalibration to prevent drift."""
        if time.monotonic() - self.last_calibration >= self.calibration_interval_secs:
            self._recalibrate()
        return self.now_micros()

    def _recalibrate(self) -> None:
        """Recalibrate the clock to prevent drift."""
        current_monotonic = time.monotonic()
        current_utc = int(time.time() * 1_000_000)

        expected_utc = self.base_timestamp_us + int(
            (current_monotonic - self.base_monotonic) * 1_000_000
        )
        drift_us = current_utc - expected_utc

        if abs(drift_us) > 1000:  # More than 1ms drift
            self.base_monotonic = current_monotonic
            self.base_timestamp_us = current_utc

        self.last_calibration = current_monotonic

    def elapsed_micros_since(self, start_timestamp_us: int) -> int:
        """Calculate elapsed microseconds from start timestamp to now."""
        return self.now_micros() - start_timestamp_us


# Global clock instance
_clock: Optional[HighPerformanceClock] = None


def get_clock() -> HighPerformanceClock:
    """Get the global high-performance clock instance."""
    global _clock
    if _clock is None:
        _clock = HighPerformanceClock()
    return _clock


def now_micros() -> int:
    """Current time in microseconds (UTC scale)."""
    return get_clock().now_micros()


def now_micros_with_calibration() -> int:
    """Current time with automatic recalibration."""
    return get_clock().now_micros_with_calibration()


def elapsed_micros_since(start_timestamp_us: int) -> int:
    """Elapsed microseconds from start timestamp to now."""
    return get_clock().elapsed_micros_since(start_timestamp_us)
