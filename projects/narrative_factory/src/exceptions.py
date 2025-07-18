"""
Comprehensive exception handling system for the Narrative Factory application.

Provides structured exceptions, retry mechanisms, and graceful error handling
for all application components.
"""

import asyncio
import functools
import time
from enum import Enum
from typing import Any, Callable, Optional

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors for classification and handling."""
    CONFIGURATION = "configuration"
    NETWORK = "network"
    DATABASE = "database"
    AI_MODEL = "ai_model"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    RESOURCE = "resource"
    BUSINESS_LOGIC = "business_logic"
    SYSTEM = "system"


class ErrorSeverity(str, Enum):
    """Severity levels for error classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NarrativeFactoryError(Exception):
    """Base exception for all Narrative Factory errors."""

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[dict[str, Any]] = None,
        recoverable: bool = True
    ):
        """Initialize error with structured information."""
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.recoverable = recoverable
        self.timestamp = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary for logging/serialization."""
        return {
            "error_message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp,
            "exception_type": self.__class__.__name__
        }


class ConfigurationError(NarrativeFactoryError):
    """Error in application configuration."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            details=details,
            recoverable=False
        )


class NetworkError(NarrativeFactoryError):
    """Network-related errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            recoverable=True
        )


class DatabaseError(NarrativeFactoryError):
    """Database operation errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            details=details,
            recoverable=True
        )


class AIModelError(NarrativeFactoryError):
    """AI model operation errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.AI_MODEL,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            recoverable=True
        )


class ValidationError(NarrativeFactoryError):
    """Data validation errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.LOW,
            details=details,
            recoverable=False
        )


class AuthenticationError(NarrativeFactoryError):
    """Authentication and authorization errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            details=details,
            recoverable=False
        )


class RateLimitError(NarrativeFactoryError):
    """Rate limiting errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.LOW,
            details=details,
            recoverable=True
        )


class ResourceError(NarrativeFactoryError):
    """Resource availability errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            recoverable=True
        )


class BusinessLogicError(NarrativeFactoryError):
    """Business logic validation errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.LOW,
            details=details,
            recoverable=False
        )


class SystemError(NarrativeFactoryError):
    """System-level errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.CRITICAL,
            details=details,
            recoverable=False
        )


class RetryConfig:
    """Configuration for retry mechanisms."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Optional[list[type[Exception]]] = None
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions or [
            NetworkError,
            DatabaseError,
            AIModelError,
            RateLimitError,
            ResourceError
        ]


class ErrorHandler:
    """Centralized error handling with retry and recovery mechanisms."""

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        """Initialize error handler with retry configuration."""
        self.retry_config = retry_config or RetryConfig()
        self.error_counts: dict[str, int] = {}
        self.last_errors: dict[str, float] = {}

    def handle_error(self, error: Exception, context: Optional[dict[str, Any]] = None) -> None:
        """Handle an error with logging and tracking."""
        context = context or {}

        # Convert to structured error if needed
        if isinstance(error, NarrativeFactoryError):
            structured_error = error
        else:
            structured_error = self._convert_to_structured_error(error)

        # Log the error
        self._log_error(structured_error, context)

        # Track error frequency
        self._track_error(structured_error)

        # Handle circuit breaker logic
        self._check_circuit_breaker(structured_error)

    def _convert_to_structured_error(self, error: Exception) -> NarrativeFactoryError:
        """Convert generic exceptions to structured errors."""
        error_type = type(error).__name__
        error_message = str(error)

        # Map common exceptions to structured errors
        if 'connection' in error_message.lower() or 'network' in error_message.lower():
            return NetworkError(error_message, details={"original_type": error_type})
        elif 'database' in error_message.lower() or 'qdrant' in error_message.lower():
            return DatabaseError(error_message, details={"original_type": error_type})
        elif 'api' in error_message.lower() or 'model' in error_message.lower():
            return AIModelError(error_message, details={"original_type": error_type})
        elif 'rate' in error_message.lower() or 'limit' in error_message.lower():
            return RateLimitError(error_message, details={"original_type": error_type})
        elif 'auth' in error_message.lower() or 'permission' in error_message.lower():
            return AuthenticationError(error_message, details={"original_type": error_type})
        else:
            return SystemError(error_message, details={"original_type": error_type})

    def _log_error(self, error: NarrativeFactoryError, context: dict[str, Any]) -> None:
        """Log error with structured information."""
        log_data = error.to_dict()
        log_data.update(context)

        if error.severity == ErrorSeverity.CRITICAL:
            logger.critical(f"Critical error: {error.message}", extra=log_data)
        elif error.severity == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {error.message}", extra=log_data)
        elif error.severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {error.message}", extra=log_data)
        else:
            logger.info(f"Low severity error: {error.message}", extra=log_data)

    def _track_error(self, error: NarrativeFactoryError) -> None:
        """Track error frequency for monitoring."""
        error_key = f"{error.category.value}:{error.__class__.__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = time.time()

    def _check_circuit_breaker(self, error: NarrativeFactoryError) -> None:
        """Check if circuit breaker should be triggered."""
        error_key = f"{error.category.value}:{error.__class__.__name__}"

        # Simple circuit breaker: too many errors in short time
        if self.error_counts.get(error_key, 0) > 10:
            last_error_time = self.last_errors.get(error_key, 0)
            if time.time() - last_error_time < 300:  # 5 minutes
                logger.critical(
                    f"Circuit breaker triggered for {error_key}",
                    extra={"error_count": self.error_counts[error_key]}
                )

    def get_error_stats(self) -> dict[str, Any]:
        """Get error statistics for monitoring."""
        return {
            "error_counts": self.error_counts.copy(),
            "last_errors": self.last_errors.copy(),
            "total_errors": sum(self.error_counts.values())
        }


# Global error handler instance
error_handler = ErrorHandler()


def handle_errors(
    reraise: bool = True,
    log_context: Optional[dict[str, Any]] = None,
    return_default: Any = None
):
    """Decorator for handling errors in functions."""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, log_context)
                if reraise:
                    raise
                return return_default

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, log_context)
                if reraise:
                    raise
                return return_default

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def with_retry(
    max_attempts: Optional[int] = None,
    base_delay: Optional[float] = None,
    max_delay: Optional[float] = None,
    retryable_exceptions: Optional[list[type[Exception]]] = None
):
    """Decorator for adding retry logic to functions."""
    retry_config = RetryConfig(
        max_attempts=max_attempts or config.app.retry_attempts,
        base_delay=base_delay or 1.0,
        max_delay=max_delay or 60.0,
        retryable_exceptions=retryable_exceptions
    )

    def decorator(func):
        @retry(
            stop=stop_after_attempt(retry_config.max_attempts),
            wait=wait_exponential(
                multiplier=retry_config.base_delay,
                max=retry_config.max_delay
            ),
            retry=retry_if_exception_type(tuple(retry_config.retryable_exceptions)),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, {"function": func.__name__})
                raise

        @retry(
            stop=stop_after_attempt(retry_config.max_attempts),
            wait=wait_exponential(
                multiplier=retry_config.base_delay,
                max=retry_config.max_delay
            ),
            retry=retry_if_exception_type(tuple(retry_config.retryable_exceptions)),
            before_sleep=before_sleep_log(logger, logging.WARNING)
        )
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_handler.handle_error(e, {"function": func.__name__})
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def graceful_degradation(fallback_func: Callable, max_failures: int = 3):
    """Decorator for implementing graceful degradation."""
    failure_count = 0

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal failure_count

            if failure_count >= max_failures:
                logger.warning(f"Using fallback for {func.__name__} due to repeated failures")
                return await fallback_func(*args, **kwargs)

            try:
                result = await func(*args, **kwargs)
                failure_count = 0  # Reset on success
                return result
            except Exception as e:
                failure_count += 1
                error_handler.handle_error(e, {"function": func.__name__})

                if failure_count >= max_failures:
                    logger.warning(f"Switching to fallback for {func.__name__}")
                    return await fallback_func(*args, **kwargs)
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal failure_count

            if failure_count >= max_failures:
                logger.warning(f"Using fallback for {func.__name__} due to repeated failures")
                return fallback_func(*args, **kwargs)

            try:
                result = func(*args, **kwargs)
                failure_count = 0  # Reset on success
                return result
            except Exception as e:
                failure_count += 1
                error_handler.handle_error(e, {"function": func.__name__})

                if failure_count >= max_failures:
                    logger.warning(f"Switching to fallback for {func.__name__}")
                    return fallback_func(*args, **kwargs)
                raise

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# Import logging to fix the reference in the retry decorator
import logging

logger.info("Exception handling system initialized")
