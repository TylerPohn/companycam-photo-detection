"""Unit tests for Retry Manager"""

import pytest
import time
from unittest.mock import Mock, patch

from src.workers.retry_manager import RetryManager, retry_with_backoff


class TestRetryManager:
    """Test retry manager functionality"""

    def test_calculate_delay_first_attempt(self):
        """Test delay calculation for first attempt (immediate)"""
        retry_manager = RetryManager()
        delay = retry_manager.calculate_delay(attempt=1)
        assert delay == 0.0

    def test_calculate_delay_second_attempt(self):
        """Test delay calculation for second attempt (1 second + jitter)"""
        retry_manager = RetryManager()
        delay = retry_manager.calculate_delay(attempt=2)

        # Should be ~1 second with jitter (0.7-1.3 seconds)
        assert 0.7 <= delay <= 1.5

    def test_calculate_delay_third_attempt(self):
        """Test delay calculation for third attempt (2 seconds + jitter)"""
        retry_manager = RetryManager()
        delay = retry_manager.calculate_delay(attempt=3)

        # Should be ~2 seconds with jitter (1.4-2.6 seconds)
        assert 1.4 <= delay <= 3.0

    def test_calculate_delay_fourth_attempt(self):
        """Test delay calculation for fourth attempt (4 seconds + jitter)"""
        retry_manager = RetryManager()
        delay = retry_manager.calculate_delay(attempt=4)

        # Should be ~4 seconds with jitter (2.8-5.2 seconds)
        assert 2.8 <= delay <= 6.0

    def test_should_retry_within_limit(self):
        """Test should_retry returns True when within retry limit"""
        retry_manager = RetryManager(max_retries=4)

        # Transient error
        error = TimeoutError("Connection timeout")
        should_retry = retry_manager.should_retry(attempt=2, error=error)
        assert should_retry is True

    def test_should_retry_max_retries_exceeded(self):
        """Test should_retry returns False when max retries exceeded"""
        retry_manager = RetryManager(max_retries=4)

        error = TimeoutError("Connection timeout")
        should_retry = retry_manager.should_retry(attempt=4, error=error)
        assert should_retry is False

    def test_should_retry_permanent_error(self):
        """Test should_retry returns False for permanent errors"""
        retry_manager = RetryManager()

        # Permanent error
        error = ValueError("Invalid schema")
        should_retry = retry_manager.should_retry(attempt=2, error=error)
        assert should_retry is False

    def test_is_transient_error_timeout(self):
        """Test timeout errors are classified as transient"""
        error = TimeoutError("Connection timeout")
        assert RetryManager.is_transient_error(error) is True

    def test_is_transient_error_connection(self):
        """Test connection errors are classified as transient"""
        error = ConnectionError("Connection refused")
        assert RetryManager.is_transient_error(error) is True

    def test_is_transient_error_validation(self):
        """Test validation errors are classified as permanent"""
        error = ValueError("Validation failed")
        assert RetryManager.is_transient_error(error) is False

    def test_is_transient_error_not_found(self):
        """Test not found errors are classified as permanent"""
        error = Exception("Photo not found - 404")
        assert RetryManager.is_transient_error(error) is False

    def test_retry_with_backoff_success_first_attempt(self):
        """Test retry_with_backoff succeeds on first attempt"""
        retry_manager = RetryManager()
        mock_func = Mock(return_value="success")

        result = retry_manager.retry_with_backoff(mock_func, arg1="test")

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_with_backoff_success_after_retries(self):
        """Test retry_with_backoff succeeds after transient failures"""
        retry_manager = RetryManager(base_delay=0.01)  # Fast delays for testing

        # Fail twice, then succeed
        mock_func = Mock(side_effect=[
            TimeoutError("timeout"),
            TimeoutError("timeout"),
            "success"
        ])

        result = retry_manager.retry_with_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    def test_retry_with_backoff_permanent_error(self):
        """Test retry_with_backoff fails immediately on permanent error"""
        retry_manager = RetryManager()

        mock_func = Mock(side_effect=ValueError("Invalid data"))

        with pytest.raises(ValueError, match="Invalid data"):
            retry_manager.retry_with_backoff(mock_func)

        # Should only be called once
        assert mock_func.call_count == 1

    def test_retry_with_backoff_max_retries_exhausted(self):
        """Test retry_with_backoff fails after max retries"""
        retry_manager = RetryManager(max_retries=3, base_delay=0.01)

        # Always fail with transient error
        mock_func = Mock(side_effect=TimeoutError("timeout"))

        with pytest.raises(TimeoutError, match="timeout"):
            retry_manager.retry_with_backoff(mock_func)

        assert mock_func.call_count == 3

    def test_retry_with_backoff_callback(self):
        """Test retry_with_backoff calls on_retry callback"""
        retry_manager = RetryManager(base_delay=0.01)

        mock_callback = Mock()
        mock_func = Mock(side_effect=[
            TimeoutError("timeout"),
            "success"
        ])

        result = retry_manager.retry_with_backoff(
            mock_func,
            on_retry=mock_callback
        )

        assert result == "success"
        assert mock_callback.call_count == 1

        # Verify callback was called with correct arguments
        call_args = mock_callback.call_args[0]
        assert call_args[0] == 1  # attempt number
        assert isinstance(call_args[1], TimeoutError)

    def test_decorator_success(self):
        """Test @retry_with_backoff decorator"""
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def test_function():
            return "success"

        result = test_function()
        assert result == "success"

    def test_decorator_with_retries(self):
        """Test decorator retries on transient errors"""
        call_count = 0

        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("timeout")
            return "success"

        result = test_function()
        assert result == "success"
        assert call_count == 3

    def test_custom_max_retries(self):
        """Test custom max_retries configuration"""
        retry_manager = RetryManager(max_retries=2)

        mock_func = Mock(side_effect=TimeoutError("timeout"))

        with pytest.raises(TimeoutError):
            retry_manager.retry_with_backoff(mock_func)

        # Should try exactly 2 times
        assert mock_func.call_count == 2

    def test_custom_base_delay(self):
        """Test custom base_delay configuration"""
        retry_manager = RetryManager(base_delay=0.5)

        delay = retry_manager.calculate_delay(attempt=2)

        # Should be ~0.5 seconds with jitter (0.35-0.65 seconds)
        assert 0.35 <= delay <= 0.8
