"""
Production-ready logging system for the Narrative Factory application.

Provides structured logging with rotation, multiple handlers, performance monitoring,
and environment-specific configurations.
"""

import json
import logging
import logging.handlers
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Optional, Union

from src.config import config


# Optional psutil import for performance monitoring
try:
    import psutil
except ImportError:
    psutil = None

# Context variables for request tracking
request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id: ContextVar[Optional[str]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context variables if available
        if request_id.get():
            log_entry["request_id"] = request_id.get()
        if user_id.get():
            log_entry["user_id"] = user_id.get()

        # Add exception info if present
        if record.exc_info:
            exc_type, exc_value, exc_traceback = record.exc_info
            log_entry["exception"] = {
                "type": exc_type.__name__ if exc_type else "Unknown",
                "message": str(exc_value) if exc_value else "",
                "traceback": traceback.format_exception(exc_type, exc_value, exc_traceback)
            }

        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'exc_info', 'exc_text', 'stack_info'
            }:
                extra_fields[key] = value

        if extra_fields:
            log_entry["extra"] = extra_fields

        return json.dumps(log_entry, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for development and console output."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        formatted = super().format(record)

        # Add context if available
        context_parts = []
        if request_id.get():
            context_parts.append(f"req:{request_id.get()}")
        if user_id.get():
            context_parts.append(f"user:{user_id.get()}")

        if context_parts:
            formatted = f"[{' | '.join(context_parts)}] {formatted}"

        return formatted


class PerformanceFilter(logging.Filter):
    """Filter to add performance metrics to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add performance context to log records."""
        # Add memory usage if available
        try:
            if psutil:
                process = psutil.Process()
                record.memory_mb = round(process.memory_info().rss / 1024 / 1024, 2)
                record.cpu_percent = process.cpu_percent()
        except Exception:
            pass

        return True


class LoggerManager:
    """Centralized logger management with configuration-driven setup."""

    def __init__(self) -> None:
        """Initialize logger manager."""
        self._loggers: dict[str, logging.Logger] = {}
        self._setup_root_logger()
        self._setup_handlers()

    def _setup_root_logger(self) -> None:
        """Configure the root logger."""
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.app.log_level.value))

        # Clear existing handlers to avoid duplicates
        root_logger.handlers.clear()

    def _setup_handlers(self) -> None:
        """Setup logging handlers based on configuration."""
        handlers: list[logging.Handler] = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        if config.app.is_development:
            console_handler.setFormatter(HumanReadableFormatter())
        else:
            console_handler.setFormatter(StructuredFormatter())
        console_handler.addFilter(PerformanceFilter())
        handlers.append(console_handler)

        # File handler with rotation
        if config.app.log_rotation:
            file_handler = logging.handlers.RotatingFileHandler(
                config.app.log_file,
                maxBytes=self._parse_size(config.app.log_max_size),
                backupCount=config.app.log_backup_count,
                encoding='utf-8'
            )
        else:
            file_handler = logging.FileHandler(
                config.app.log_file,
                encoding='utf-8'
            )

        file_handler.setFormatter(StructuredFormatter())
        file_handler.addFilter(PerformanceFilter())
        handlers.append(file_handler)

        # Error file handler (errors and above only)
        error_file = config.app.log_file.parent / f"{config.app.log_file.stem}_errors.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        handlers.append(error_handler)

        # Add all handlers to root logger
        root_logger = logging.getLogger()
        for handler in handlers:
            root_logger.addHandler(handler)

    def _parse_size(self, size_str: str) -> int:
        """Parse size string (e.g., '10MB') to bytes."""
        units = {
            'B': 1,
            'KB': 1024,
            'MB': 1024 ** 2,
            'GB': 1024 ** 3,
        }

        size_str = size_str.upper().strip()
        # Check units in order of length (longest first) to avoid MB being matched as B
        for unit in sorted(units.keys(), key=len, reverse=True):
            if size_str.endswith(unit):
                number_part = size_str[:-len(unit)].strip()
                if number_part:
                    return int(number_part) * units[unit]

        # Default to bytes if no unit specified
        return int(size_str)

    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger with the specified name."""
        if name not in self._loggers:
            logger = logging.getLogger(name)
            self._loggers[name] = logger

        return self._loggers[name]

    def set_level(self, level: Union[str, int]) -> None:
        """Set the logging level for all loggers."""
        if isinstance(level, str):
            level = getattr(logging, level.upper())

        root_logger = logging.getLogger()
        root_logger.setLevel(level)

        for handler in root_logger.handlers:
            if handler.level < int(level):
                handler.setLevel(level)


# Global logger manager instance
logger_manager = LoggerManager()


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for the specified name."""
    return logger_manager.get_logger(name)


def log_execution_time(logger_name: Optional[str] = None) -> Callable:
    """Decorator to log function execution time."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(logger_name or func.__module__)
            start_time = datetime.now(timezone.utc)

            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"Function {func.__name__} completed",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "func_module": func.__module__
                    }
                )
                return result
            except Exception as e:
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    f"Function {func.__name__} failed",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "module": func.__module__,
                        "error": str(e)
                    },
                    exc_info=True
                )
                raise

        return wrapper
    return decorator


def log_api_call(logger_name: Optional[str] = None) -> Callable:
    """Decorator to log API calls with request/response details."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = get_logger(logger_name or func.__module__)
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting API call: {func.__name__}",
                extra={
                    "function_name": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
            )

            try:
                result = await func(*args, **kwargs)
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"API call completed: {func.__name__}",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "success": True
                    }
                )
                return result
            except Exception as e:
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    f"API call failed: {func.__name__}",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "error": str(e),
                        "success": False
                    },
                    exc_info=True
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(logger_name or func.__module__)
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting API call: {func.__name__}",
                extra={
                    "function_name": func.__name__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
            )

            try:
                result = func(*args, **kwargs)
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"API call completed: {func.__name__}",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "success": True
                    }
                )
                return result
            except Exception as e:
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                logger.error(
                    f"API call failed: {func.__name__}",
                    extra={
                        "execution_time_seconds": execution_time,
                        "function_name": func.__name__,
                        "error": str(e),
                        "success": False
                    },
                    exc_info=True
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class LogContext:
    """Context manager for setting logging context variables."""

    def __init__(self, **context):
        """Initialize with context variables."""
        self.context = context
        self.tokens = {}

    def __enter__(self):
        """Set context variables."""
        if 'request_id' in self.context:
            self.tokens['request_id'] = request_id.set(self.context['request_id'])
        if 'user_id' in self.context:
            self.tokens['user_id'] = user_id.set(self.context['user_id'])
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Reset context variables."""
        for token in self.tokens.values():
            token.var.set(token.old_value)


# Convenience function for setting log context
def set_log_context(**context) -> LogContext:
    """Set logging context variables."""
    return LogContext(**context)


# Module-level logger for this file
logger = get_logger(__name__)
logger.info("Logging system initialized", extra={"config_validated": True})
