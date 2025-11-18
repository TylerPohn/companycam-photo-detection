"""Retry manager with exponential backoff for message processing"""

import logging
import time
import random
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)


class RetryManager:
    """
    Manages retry logic with exponential backoff and jitter.

    Implements retry strategy:
    - Attempt 1: Immediate
    - Attempt 2: Retry after 1 second
    - Attempt 3: Retry after 2 seconds
    - Attempt 4: Retry after 4 seconds
    - After 4 attempts: Move to DLQ
    """

    # Retry configuration
    MAX_RETRIES = 4
    BASE_DELAY = 1.0  # 1 second base delay
    MAX_JITTER = 0.3  # 30% jitter to prevent thundering herd

    def __init__(self, max_retries: int = MAX_RETRIES, base_delay: float = BASE_DELAY):
        """
        Initialize retry manager.

        Args:
            max_retries: Maximum number of retry attempts (default: 4)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given retry attempt with exponential backoff and jitter.

        Formula: delay = base_delay * (2 ^ (attempt - 1)) + jitter
        - Attempt 1: 0 seconds (immediate)
        - Attempt 2: 1 second + jitter
        - Attempt 3: 2 seconds + jitter
        - Attempt 4: 4 seconds + jitter

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if attempt <= 1:
            return 0.0

        # Exponential backoff: 2^(attempt-2) * base_delay
        # attempt 2: 2^0 = 1 second
        # attempt 3: 2^1 = 2 seconds
        # attempt 4: 2^2 = 4 seconds
        delay = self.base_delay * (2 ** (attempt - 2))

        # Add jitter to prevent thundering herd
        jitter = random.uniform(0, self.MAX_JITTER * delay)
        total_delay = delay + jitter

        logger.debug(f"Calculated retry delay for attempt {attempt}: {total_delay:.2f}s")
        return total_delay

    def should_retry(self, attempt: int, error: Exception) -> bool:
        """
        Determine if operation should be retried based on attempt count and error type.

        Args:
            attempt: Current attempt number (1-indexed)
            error: Exception that occurred

        Returns:
            True if should retry, False otherwise
        """
        if attempt >= self.max_retries:
            logger.warning(f"Max retries ({self.max_retries}) reached, will not retry")
            return False

        # Check if error is transient (should retry)
        if self.is_transient_error(error):
            logger.info(f"Transient error detected, will retry (attempt {attempt}/{self.max_retries})")
            return True

        # Permanent error - don't retry
        logger.error(f"Permanent error detected, will not retry: {type(error).__name__}")
        return False

    @staticmethod
    def is_transient_error(error: Exception) -> bool:
        """
        Determine if error is transient and should be retried.

        Transient errors (retry):
        - Network timeouts
        - Connection errors
        - Temporary service unavailability
        - Rate limiting

        Permanent errors (don't retry):
        - Validation errors
        - Data not found
        - Invalid schema
        - Authorization errors

        Args:
            error: Exception to classify

        Returns:
            True if transient, False if permanent
        """
        error_name = type(error).__name__
        error_msg = str(error).lower()

        # Transient error indicators
        transient_indicators = [
            "timeout",
            "connection",
            "network",
            "unavailable",
            "503",
            "502",
            "504",
            "rate limit",
            "throttl",
        ]

        # Permanent error indicators
        permanent_indicators = [
            "validation",
            "not found",
            "404",
            "401",
            "403",
            "invalid",
            "schema",
            "malformed",
        ]

        # Check for permanent errors first
        for indicator in permanent_indicators:
            if indicator in error_msg or indicator in error_name.lower():
                return False

        # Check for transient errors
        for indicator in transient_indicators:
            if indicator in error_msg or indicator in error_name.lower():
                return True

        # Default to transient for unknown errors (safer to retry)
        logger.warning(f"Unknown error type, treating as transient: {error_name}")
        return True

    def retry_with_backoff(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[int, Exception], None]] = None,
        **kwargs
    ) -> Any:
        """
        Execute function with retry and exponential backoff.

        Args:
            func: Function to execute
            *args: Positional arguments for func
            on_retry: Optional callback called on each retry with (attempt, error)
            **kwargs: Keyword arguments for func

        Returns:
            Result of successful function execution

        Raises:
            Last exception if all retries are exhausted
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                func_name = getattr(func, '__name__', 'unknown')
                logger.debug(f"Attempt {attempt}/{self.max_retries} for {func_name}")
                result = func(*args, **kwargs)

                if attempt > 1:
                    logger.info(f"Success on attempt {attempt} for {func_name}")

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Attempt {attempt}/{self.max_retries} failed for {func.__name__}: {e}"
                )

                # Call retry callback if provided
                if on_retry:
                    try:
                        on_retry(attempt, e)
                    except Exception as callback_error:
                        logger.error(f"Error in retry callback: {callback_error}")

                # Check if should retry
                if not self.should_retry(attempt, e):
                    logger.error(f"Not retrying due to permanent error: {e}")
                    raise e

                # Don't delay after last attempt
                if attempt < self.max_retries:
                    delay = self.calculate_delay(attempt + 1)
                    if delay > 0:
                        logger.debug(f"Waiting {delay:.2f}s before next retry")
                        time.sleep(delay)

        # All retries exhausted
        func_name = getattr(func, '__name__', 'unknown')
        logger.error(f"All {self.max_retries} attempts failed for {func_name}")
        raise last_error


def retry_with_backoff(
    max_retries: int = RetryManager.MAX_RETRIES,
    base_delay: float = RetryManager.BASE_DELAY
):
    """
    Decorator for automatic retry with exponential backoff.

    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def my_function():
            # function code
            pass

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retry_manager = RetryManager(max_retries=max_retries, base_delay=base_delay)
            return retry_manager.retry_with_backoff(func, *args, **kwargs)
        return wrapper
    return decorator
