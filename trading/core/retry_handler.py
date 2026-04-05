"""
Retry handling for failed transactions.

Provides configurable retry strategies with backoff,
jitter, and circuit breaker patterns.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED = auto()
    LINEAR = auto()
    EXPONENTIAL = auto()
    EXPONENTIAL_JITTER = auto()
    DECORRELATED_JITTER = auto()


@dataclass
class RetryConfig:
    """Configuration for retry handling."""
    max_attempts: int = 3
    base_delay_ms: int = 100
    max_delay_ms: int = 30000
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    retryable_errors: List[Type[Exception]] = field(default_factory=list)
    non_retryable_errors: List[Type[Exception]] = field(default_factory=list)
    on_retry: Optional[Callable[[int, Exception], None]] = None
    on_exhausted: Optional[Callable[[Exception], None]] = None
    timeout_ms: int = 60000


@dataclass
class RetryState:
    """State of a retry operation."""
    attempt: int = 0
    last_error: Optional[Exception] = None
    total_delay_ms: int = 0
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_ms(self) -> int:
        """Get elapsed time in milliseconds."""
        return int((time.time() - self.start_time) * 1000)


class ExponentialBackoff:
    """Exponential backoff calculator."""

    def __init__(
        self,
        base_delay_ms: int = 100,
        max_delay_ms: int = 30000,
        multiplier: float = 2.0,
    ):
        self.base_delay_ms = base_delay_ms
        self.max_delay_ms = max_delay_ms
        self.multiplier = multiplier

    def calculate(self, attempt: int) -> int:
        """
        Calculate delay for attempt.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in milliseconds
        """
        delay = self.base_delay_ms * (self.multiplier ** attempt)
        return int(min(delay, self.max_delay_ms))


class JitterGenerator:
    """Jitter generation for retry delays."""

    @staticmethod
    def full_jitter(delay_ms: int) -> int:
        """Full jitter: random value between 0 and delay."""
        return random.randint(0, delay_ms)

    @staticmethod
    def equal_jitter(delay_ms: int) -> int:
        """Equal jitter: half fixed, half jittered."""
        half = delay_ms // 2
        return half + random.randint(0, half)

    @staticmethod
    def decorrelated_jitter(
        last_delay_ms: int,
        base_delay_ms: int,
        max_delay_ms: int,
    ) -> int:
        """Decorrelated jitter: 3 * base to last * 3."""
        return min(
            max_delay_ms,
            random.randint(base_delay_ms, last_delay_ms * 3)
        )


class CircuitBreaker:
    """
    Circuit breaker pattern for fault tolerance.

    Prevents cascading failures by stopping retries
    when failure rate is too high.
    """

    class State(Enum):
        CLOSED = auto()  # Normal operation
        OPEN = auto()    # Failing, reject requests
        HALF_OPEN = auto()  # Testing if recovered

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_ms: int = 30000,
        success_threshold: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_ms = recovery_timeout_ms
        self.success_threshold = success_threshold

        self._state = self.State.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> State:
        """Get current circuit state."""
        return self._state

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Call function with circuit breaker protection.

        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        async with self._lock:
            if self._state == self.State.OPEN:
                # Check if recovery timeout passed
                if self._last_failure_time:
                    elapsed = (time.time() - self._last_failure_time) * 1000
                    if elapsed > self.recovery_timeout_ms:
                        self._state = self.State.HALF_OPEN
                        self._success_count = 0
                    else:
                        raise CircuitBreakerOpen("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == self.State.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = self.State.CLOSED
                    self._failure_count = 0
            else:
                self._failure_count = 0

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == self.State.HALF_OPEN:
                self._state = self.State.OPEN
            elif self._failure_count >= self.failure_threshold:
                self._state = self.State.OPEN

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "state": self._state.name,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure_time": self._last_failure_time,
        }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""
    pass


class RetryHandler:
    """
    Handle retries with configurable strategies.

    Features:
    - Multiple retry strategies
    - Jitter to prevent thundering herd
    - Circuit breaker integration
    - Per-error-type configuration
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._backoff = ExponentialBackoff(
            base_delay_ms=self.config.base_delay_ms,
            max_delay_ms=self.config.max_delay_ms,
        )
        self._jitter = JitterGenerator()
        self._last_delay_ms = self.config.base_delay_ms

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """
        Execute function with retries.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retries exhausted
        """
        state = RetryState()

        while state.attempt < self.config.max_attempts:
            try:
                # Check timeout
                if state.elapsed_ms > self.config.timeout_ms:
                    raise RetryTimeout(f"Retry timeout after {state.elapsed_ms}ms")

                return await func(*args, **kwargs)

            except Exception as e:
                state.last_error = e

                # Check if error is retryable
                if not self._is_retryable(e):
                    raise

                state.attempt += 1

                if state.attempt >= self.config.max_attempts:
                    break

                # Calculate delay
                delay_ms = self._calculate_delay(state.attempt)
                state.total_delay_ms += delay_ms

                # Notify retry callback
                if self.config.on_retry:
                    try:
                        if asyncio.iscoroutinefunction(self.config.on_retry):
                            await self.config.on_retry(state.attempt, e)
                        else:
                            self.config.on_retry(state.attempt, e)
                    except Exception as cb_err:
                        logger.error(f"Retry callback error: {cb_err}")

                # Wait before retry
                await asyncio.sleep(delay_ms / 1000)

        # All retries exhausted
        if self.config.on_exhausted:
            try:
                if asyncio.iscoroutinefunction(self.config.on_exhausted):
                    await self.config.on_exhausted(state.last_error)
                else:
                    self.config.on_exhausted(state.last_error)
            except Exception as cb_err:
                logger.error(f"Exhausted callback error: {cb_err}")

        raise RetryExhausted(
            f"All {self.config.max_attempts} attempts failed",
            state.last_error,
        ) from state.last_error

    def _is_retryable(self, error: Exception) -> bool:
        """Check if error is retryable."""
        # Check non-retryable first
        for error_type in self.config.non_retryable_errors:
            if isinstance(error, error_type):
                return False

        # Check retryable
        if self.config.retryable_errors:
            for error_type in self.config.retryable_errors:
                if isinstance(error, error_type):
                    return True
            return False

        # Default: retry all
        return True

    def _calculate_delay(self, attempt: int) -> int:
        """Calculate retry delay."""
        strategy = self.config.strategy

        if strategy == RetryStrategy.FIXED:
            delay = self.config.base_delay_ms

        elif strategy == RetryStrategy.LINEAR:
            delay = self.config.base_delay_ms * attempt

        elif strategy == RetryStrategy.EXPONENTIAL:
            delay = self._backoff.calculate(attempt - 1)

        elif strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base_delay = self._backoff.calculate(attempt - 1)
            delay = self._jitter.equal_jitter(base_delay)

        elif strategy == RetryStrategy.DECORRELATED_JITTER:
            delay = self._jitter.decorrelated_jitter(
                self._last_delay_ms,
                self.config.base_delay_ms,
                self.config.max_delay_ms,
            )
            self._last_delay_ms = delay

        else:
            delay = self.config.base_delay_ms

        return int(min(delay, self.config.max_delay_ms))


class RetryExhausted(Exception):
    """Exception raised when all retries are exhausted."""

    def __init__(self, message: str, last_error: Optional[Exception] = None):
        super().__init__(message)
        self.last_error = last_error


class RetryTimeout(Exception):
    """Exception raised when retry timeout is reached."""
    pass


class BatchRetryHandler:
    """Handle retries for batch operations."""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()
        self._handler = RetryHandler(self.config)

    async def execute_batch(
        self,
        funcs: List[Callable[..., T]],
        *args,
        **kwargs,
    ) -> List[Union[T, Exception]]:
        """
        Execute multiple functions with individual retries.

        Args:
            funcs: List of functions to execute
            *args: Arguments for each function
            **kwargs: Keyword arguments for each function

        Returns:
            List of results or exceptions
        """
        tasks = [
            self._execute_single(func, *args, **kwargs)
            for func in funcs
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def _execute_single(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute single function with retry."""
        try:
            return await self._handler.execute(func, *args, **kwargs)
        except Exception as e:
            return e

    async def execute_batch_all_or_nothing(
        self,
        func: Callable[..., List[T]],
        *args,
        **kwargs,
    ) -> List[T]:
        """
        Execute batch function with retry (all-or-nothing).

        Args:
            func: Function that returns list of results
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            List of results

        Raises:
            Exception: If any retry fails
        """
        return await self._handler.execute(func, *args, **kwargs)


class AdaptiveRetryHandler(RetryHandler):
    """
    Adaptive retry handler that adjusts strategy based on success rate.
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        super().__init__(config)
        self._success_count = 0
        self._failure_count = 0
        self._adaptive_multiplier = 1.0

    async def execute(
        self,
        func: Callable[..., T],
        *args,
        **kwargs,
    ) -> T:
        """Execute with adaptive retry."""
        try:
            result = await super().execute(func, *args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _on_success(self) -> None:
        """Handle successful execution."""
        self._success_count += 1
        # Decrease delays on success
        self._adaptive_multiplier = max(0.5, self._adaptive_multiplier * 0.95)

    def _on_failure(self) -> None:
        """Handle failed execution."""
        self._failure_count += 1
        # Increase delays on failure
        self._adaptive_multiplier = min(2.0, self._adaptive_multiplier * 1.05)

    def _calculate_delay(self, attempt: int) -> int:
        """Calculate delay with adaptive multiplier."""
        base_delay = super()._calculate_delay(attempt)
        return int(base_delay * self._adaptive_multiplier)

    def get_stats(self) -> Dict[str, Any]:
        """Get adaptive handler statistics."""
        total = self._success_count + self._failure_count
        success_rate = self._success_count / total if total > 0 else 0

        return {
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "success_rate": success_rate,
            "adaptive_multiplier": self._adaptive_multiplier,
        }
