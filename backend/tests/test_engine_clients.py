"""Unit tests for engine clients and circuit breaker"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
import httpx

from src.services.engine_clients import (
    CircuitBreaker,
    EngineClient,
    LoadBalancedEngineClient,
)
from src.schemas.orchestrator import (
    DetectionType,
    CircuitBreakerState,
    EngineResult,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker pattern"""

    def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes in closed state"""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout_seconds=60)

        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0
        assert cb.can_attempt() is True

    def test_circuit_breaker_opens_after_threshold(self):
        """Test circuit breaker opens after failure threshold"""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures
        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_attempt() is False

    def test_circuit_breaker_resets_on_success(self):
        """Test circuit breaker resets failure count on success"""
        cb = CircuitBreaker(failure_threshold=5)

        # Record some failures
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

        # Success resets count
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED

    def test_circuit_breaker_half_open_transition(self):
        """Test circuit breaker transitions to half-open after timeout"""
        cb = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout_seconds=1  # Short timeout for testing
        )

        # Open the circuit
        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitBreakerState.OPEN
        assert cb.can_attempt() is False

        # Wait for recovery timeout
        import time
        time.sleep(1.1)

        # Should transition to half-open
        assert cb.can_attempt() is True
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_circuit_breaker_half_open_success_closes(self):
        """Test circuit breaker closes after successful half-open request"""
        cb = CircuitBreaker(failure_threshold=3)

        # Force to half-open
        cb.state = CircuitBreakerState.HALF_OPEN

        # Success should close circuit
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_half_open_failure_reopens(self):
        """Test circuit breaker reopens after failed half-open attempts"""
        cb = CircuitBreaker(failure_threshold=3, half_open_max_attempts=2)

        # Force to half-open
        cb.state = CircuitBreakerState.HALF_OPEN
        cb.half_open_attempts = 0

        # Record failures
        cb.record_failure()
        assert cb.state == CircuitBreakerState.HALF_OPEN  # Still half-open after 1st

        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN  # Opens after 2nd


class TestEngineClient:
    """Tests for EngineClient"""

    @pytest.fixture
    def engine_client(self):
        """Create engine client for testing"""
        return EngineClient(
            engine_type=DetectionType.DAMAGE,
            endpoint="http://test-engine:8001",
            timeout_seconds=5,
        )

    @pytest.mark.asyncio
    async def test_predict_success(self, engine_client):
        """Test successful prediction request"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model_version": "v1.0.0",
            "confidence": 0.85,
            "results": {"detections": [{"type": "damage", "score": 0.85}]},
        }
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await engine_client.predict("s3://bucket/photo.jpg")

            assert isinstance(result, EngineResult)
            assert result.engine_type == DetectionType.DAMAGE
            assert result.confidence == 0.85
            assert result.error is None

    @pytest.mark.asyncio
    async def test_predict_with_circuit_breaker_open(self, engine_client):
        """Test prediction fails when circuit breaker is open"""
        # Force circuit breaker open
        engine_client.circuit_breaker.state = CircuitBreakerState.OPEN

        result = await engine_client.predict("s3://bucket/photo.jpg")

        assert result.error is not None
        assert "Circuit breaker" in result.error
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_predict_timeout(self, engine_client):
        """Test prediction with timeout"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Request timeout")
            )

            result = await engine_client.predict("s3://bucket/photo.jpg")

            # After retries, should return error result
            assert result.error is not None
            assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_predict_records_circuit_breaker_success(self, engine_client):
        """Test successful prediction records circuit breaker success"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "model_version": "v1.0.0",
            "confidence": 0.85,
            "results": {},
        }
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            # Add some failures first
            engine_client.circuit_breaker.failure_count = 2

            await engine_client.predict("s3://bucket/photo.jpg")

            # Success should reset failure count
            assert engine_client.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_predict_records_circuit_breaker_failure(self, engine_client):
        """Test failed prediction records circuit breaker failure"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            initial_count = engine_client.circuit_breaker.failure_count

            result = await engine_client.predict("s3://bucket/photo.jpg")

            # Failure count should increase
            assert engine_client.circuit_breaker.failure_count > initial_count

    @pytest.mark.asyncio
    async def test_health_check_success(self, engine_client):
        """Test successful health check"""
        mock_response = Mock()
        mock_response.raise_for_status = Mock()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            health = await engine_client.health_check()

            assert health.healthy is True
            assert health.engine_type == DetectionType.DAMAGE
            assert health.response_time_ms is not None

    @pytest.mark.asyncio
    async def test_health_check_failure(self, engine_client):
        """Test failed health check"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection failed")
            )

            health = await engine_client.health_check()

            assert health.healthy is False
            assert health.response_time_ms is not None


class TestLoadBalancedEngineClient:
    """Tests for LoadBalancedEngineClient"""

    @pytest.fixture
    def lb_client(self):
        """Create load-balanced client for testing"""
        return LoadBalancedEngineClient(
            engine_type=DetectionType.DAMAGE,
            endpoints=[
                "http://engine-1:8001",
                "http://engine-2:8001",
                "http://engine-3:8001",
            ]
        )

    def test_load_balanced_client_initialization(self, lb_client):
        """Test load-balanced client initializes with multiple endpoints"""
        assert len(lb_client.clients) == 3
        assert lb_client.engine_type == DetectionType.DAMAGE
        assert lb_client.current_index == 0

    @pytest.mark.asyncio
    async def test_round_robin_load_balancing(self, lb_client):
        """Test round-robin load balancing across endpoints"""
        mock_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.0.0",
            confidence=0.85,
            results={},
            processing_time_ms=100,
        )

        endpoints_used = []

        async def mock_predict(photo_url, metadata=None):
            # Track which endpoint was used
            client_index = (lb_client.current_index - 1) % len(lb_client.clients)
            endpoints_used.append(client_index)
            return mock_result

        # Mock predict for all clients
        for client in lb_client.clients:
            client.predict = mock_predict

        # Make 6 requests (2 full rounds)
        for i in range(6):
            await lb_client.predict("s3://bucket/photo.jpg")

        # Should cycle through all endpoints
        assert 0 in endpoints_used
        assert 1 in endpoints_used
        assert 2 in endpoints_used

    @pytest.mark.asyncio
    async def test_load_balancing_skips_unavailable_endpoints(self, lb_client):
        """Test load balancing skips endpoints with open circuit breakers"""
        # Open circuit breaker on first client
        lb_client.clients[0].circuit_breaker.state = CircuitBreakerState.OPEN

        mock_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.0.0",
            confidence=0.85,
            results={},
            processing_time_ms=100,
        )

        # Mock predict for available clients
        for i, client in enumerate(lb_client.clients):
            if i != 0:  # Skip first client
                client.predict = AsyncMock(return_value=mock_result)

        result = await lb_client.predict("s3://bucket/photo.jpg")

        # Should successfully route to available endpoint
        assert result.error is None

    @pytest.mark.asyncio
    async def test_load_balancing_fails_when_all_unavailable(self, lb_client):
        """Test load balancing fails when all endpoints are unavailable"""
        # Open all circuit breakers
        for client in lb_client.clients:
            client.circuit_breaker.state = CircuitBreakerState.OPEN

        with pytest.raises(Exception, match="No available endpoints"):
            await lb_client.predict("s3://bucket/photo.jpg")

    @pytest.mark.asyncio
    async def test_health_check_all(self, lb_client):
        """Test health check on all endpoints"""
        from src.schemas.orchestrator import EngineHealth

        mock_health = EngineHealth(
            engine_type=DetectionType.DAMAGE,
            endpoint="http://test:8001",
            healthy=True,
            last_check=datetime.utcnow(),
            response_time_ms=50,
        )

        # Mock health check for all clients
        for client in lb_client.clients:
            client.health_check = AsyncMock(return_value=mock_health)

        health_results = await lb_client.health_check_all()

        assert len(health_results) == 3
        assert all(h.healthy for h in health_results)
