"""
Fast timing utilities for ultra-low latency operations.

Provides high-precision timing functions optimized for performance measurement.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# Use the most precise clock available
try:
    # time.perf_counter_ns is the highest precision on Python 3.7+
    _perf_counter_ns = time.perf_counter_ns
    _perf_counter = time.perf_counter
    HAS_NS_PRECISION = True
except AttributeError:
    _perf_counter_ns = None
    _perf_counter = time.perf_counter
    HAS_NS_PRECISION = False


def now_ns() -> int:
    """Get current time in nanoseconds."""
    if HAS_NS_PRECISION:
        return _perf_counter_ns()
    return int(_perf_counter() * 1_000_000_000)


def now_us() -> int:
    """Get current time in microseconds."""
    if HAS_NS_PRECISION:
        return _perf_counter_ns() // 1000
    return int(_perf_counter() * 1_000_000)


def now_ms() -> int:
    """Get current time in milliseconds."""
    if HAS_NS_PRECISION:
        return _perf_counter_ns() // 1_000_000
    return int(_perf_counter() * 1000)


def elapsed_ns(start_ns: int) -> int:
    """Calculate elapsed nanoseconds from start time."""
    return now_ns() - start_ns


def elapsed_us(start_us: int) -> int:
    """Calculate elapsed microseconds from start time."""
    return now_us() - start_us


def elapsed_ms(start_ms: int) -> int:
    """Calculate elapsed milliseconds from start time."""
    return now_ms() - start_ms


@dataclass
class TimingSample:
    """A single timing measurement."""
    name: str
    start_ns: int
    end_ns: int
    metadata: Optional[Dict] = None

    @property
    def duration_ns(self) -> int:
        return self.end_ns - self.start_ns

    @property
    def duration_us(self) -> float:
        return self.duration_ns / 1000.0

    @property
    def duration_ms(self) -> float:
        return self.duration_ns / 1_000_000.0


class Timer:
    """High-precision timer for performance measurement."""

    def __init__(self, name: str = ""):
        self.name = name
        self._start_ns: Optional[int] = None
        self._samples: List[TimingSample] = []

    def start(self) -> "Timer":
        """Start the timer."""
        self._start_ns = now_ns()
        return self

    def stop(self, metadata: Optional[Dict] = None) -> TimingSample:
        """Stop the timer and record sample."""
        if self._start_ns is None:
            raise RuntimeError("Timer not started")

        end_ns = now_ns()
        sample = TimingSample(
            name=self.name,
            start_ns=self._start_ns,
            end_ns=end_ns,
            metadata=metadata,
        )
        self._samples.append(sample)
        self._start_ns = None
        return sample

    def lap(self, lap_name: str, metadata: Optional[Dict] = None) -> TimingSample:
        """Record a lap time without stopping."""
        if self._start_ns is None:
            raise RuntimeError("Timer not started")

        end_ns = now_ns()
        sample = TimingSample(
            name=f"{self.name}.{lap_name}",
            start_ns=self._start_ns,
            end_ns=end_ns,
            metadata=metadata,
        )
        self._samples.append(sample)
        self._start_ns = end_ns  # Reset start for next lap
        return sample

    def get_samples(self) -> List[TimingSample]:
        """Get all recorded samples."""
        return self._samples.copy()

    def get_average_ns(self) -> float:
        """Get average duration in nanoseconds."""
        if not self._samples:
            return 0.0
        return sum(s.duration_ns for s in self._samples) / len(self._samples)

    def get_min_ns(self) -> int:
        """Get minimum duration in nanoseconds."""
        if not self._samples:
            return 0
        return min(s.duration_ns for s in self._samples)

    def get_max_ns(self) -> int:
        """Get maximum duration in nanoseconds."""
        if not self._samples:
            return 0
        return max(s.duration_ns for s in self._samples)

    def reset(self) -> None:
        """Reset all samples."""
        self._samples.clear()
        self._start_ns = None


class TimingContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str = "", callback: Optional[Callable[[TimingSample], None]] = None):
        self.name = name
        self.callback = callback
        self.timer = Timer(name)
        self.sample: Optional[TimingSample] = None

    def __enter__(self) -> "TimingContext":
        self.timer.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.sample = self.timer.stop(metadata={"exception": str(exc_val) if exc_val else None})
        if self.callback:
            self.callback(self.sample)


class LatencyHistogram:
    """Histogram for latency distribution tracking."""

    def __init__(self, buckets_us: Optional[List[int]] = None):
        # Default buckets: 10us, 50us, 100us, 500us, 1ms, 5ms, 10ms, 50ms, 100ms
        self.buckets_us = buckets_us or [10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000]
        self.counts: Dict[int, int] = {b: 0 for b in self.buckets_us}
        self.total_count = 0
        self.sum_us = 0

    def record(self, duration_us: int) -> None:
        """Record a duration measurement."""
        self.total_count += 1
        self.sum_us += duration_us

        for bucket in self.buckets_us:
            if duration_us <= bucket:
                self.counts[bucket] += 1
                break

    def get_percentile(self, p: float) -> int:
        """Get percentile value in microseconds."""
        if self.total_count == 0:
            return 0

        target = int(self.total_count * p)
        cumulative = 0

        for bucket in sorted(self.buckets_us):
            cumulative += self.counts[bucket]
            if cumulative >= target:
                return bucket

        return self.buckets_us[-1]

    def get_average_us(self) -> float:
        """Get average duration in microseconds."""
        if self.total_count == 0:
            return 0.0
        return self.sum_us / self.total_count

    def get_stats(self) -> Dict:
        """Get histogram statistics."""
        return {
            "count": self.total_count,
            "avg_us": self.get_average_us(),
            "p50_us": self.get_percentile(0.50),
            "p90_us": self.get_percentile(0.90),
            "p99_us": self.get_percentile(0.99),
            "buckets": self.counts.copy(),
        }


class CoarseTimer:
    """
    Coarse-grained timer for less critical timing.
    Uses faster but less precise time source.
    """

    def __init__(self):
        self._start = 0.0

    def start(self) -> None:
        """Start coarse timer."""
        self._start = time.time()

    def elapsed_ms(self) -> int:
        """Get elapsed milliseconds."""
        return int((time.time() - self._start) * 1000)


# Global timing utilities
_global_timer: Optional[Timer] = None
_global_histogram: Optional[LatencyHistogram] = None


def get_global_timer() -> Timer:
    """Get or create global timer."""
    global _global_timer
    if _global_timer is None:
        _global_timer = Timer("global")
    return _global_timer


def get_global_histogram() -> LatencyHistogram:
    """Get or create global latency histogram."""
    global _global_histogram
    if _global_histogram is None:
        _global_histogram = LatencyHistogram()
    return _global_histogram


def timed(name: str = ""):
    """Decorator for timing function execution."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            with TimingContext(name) as ctx:
                result = func(*args, **kwargs)
            return result
        return wrapper
    return decorator
