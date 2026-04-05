"""
SDK logging utilities.

Provides structured logging with performance considerations.
"""

from __future__ import annotations

import logging
import sys
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class LogLevel(Enum):
    """Log levels matching Python's logging."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL


@dataclass
class LogEntry:
    """Structured log entry."""
    level: str
    message: str
    module: str
    timestamp: float
    thread_id: int
    extra: Optional[Dict[str, Any]] = None


class StructuredFormatter(logging.Formatter):
    """Formatter for structured log output."""

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        super().__init__(fmt or "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record."""
        # Add extra fields if present
        if hasattr(record, "extra"):
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra.items())
            record.message = f"{record.getMessage()} [{extra_str}]"

        return super().format(record)


class SDKLogger:
    """
    SDK-specific logger with performance optimizations.

    Features:
    - Lazy evaluation of expensive log messages
    - Structured logging support
    - Context tracking
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def debug(self, msg: str, **kwargs) -> None:
        """Log debug message."""
        if self._logger.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs) -> None:
        """Log info message."""
        if self._logger.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        """Log warning message."""
        if self._logger.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        """Log error message."""
        if self._logger.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs) -> None:
        """Log critical message."""
        if self._logger.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, msg, **kwargs)

    def _log(self, level: int, msg: str, **kwargs) -> None:
        """Internal log method."""
        extra = {}

        with self._lock:
            if self._context:
                extra["context"] = self._context.copy()

        if kwargs:
            extra.update(kwargs)

        if extra:
            self._logger.log(level, msg, extra={"extra": extra})
        else:
            self._logger.log(level, msg)

    def set_context(self, **kwargs) -> None:
        """Set logging context."""
        with self._lock:
            self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear logging context."""
        with self._lock:
            self._context.clear()

    def with_context(self, **kwargs):
        """Context manager for temporary context."""
        return LogContext(self, **kwargs)


class LogContext:
    """Context manager for temporary logging context."""

    def __init__(self, logger: SDKLogger, **kwargs):
        self.logger = logger
        self.kwargs = kwargs
        self.prev_context: Optional[Dict] = None

    def __enter__(self):
        self.prev_context = self.logger._context.copy()
        self.logger.set_context(**self.kwargs)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger._context = self.prev_context or {}


# Module-level loggers
_sdk_loggers: Dict[str, SDKLogger] = {}


def get_logger(name: str) -> SDKLogger:
    """Get or create SDK logger."""
    if name not in _sdk_loggers:
        _sdk_loggers[name] = SDKLogger(name)
    return _sdk_loggers[name]


def setup_logging(
    level: LogLevel = LogLevel.INFO,
    format_str: Optional[str] = None,
    handler: Optional[logging.Handler] = None,
) -> None:
    """
    Setup SDK logging configuration.

    Args:
        level: Minimum log level
        format_str: Log format string
        handler: Optional custom handler
    """
    root_logger = logging.getLogger("sol_trade_sdk")
    root_logger.setLevel(level.value)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create handler if not provided
    if handler is None:
        handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    formatter = StructuredFormatter(format_str)
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)


def disable_logging() -> None:
    """Disable all SDK logging for maximum performance."""
    logging.getLogger("sol_trade_sdk").disabled = True


def enable_logging() -> None:
    """Re-enable SDK logging."""
    logging.getLogger("sol_trade_sdk").disabled = False
