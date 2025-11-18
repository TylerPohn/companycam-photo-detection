"""Clients for AI detection engines with circuit breaker pattern"""

import asyncio
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from enum import Enum

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.schemas.orchestrator import (
    DetectionType,
    EngineResult,
    CircuitBreakerState,
    EngineHealth,
    ModelVersion,
)
from src.monitoring.metrics import metrics_collector

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker pattern implementation for engine failover"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
        half_open_max_attempts: int = 3,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_attempts = half_open_max_attempts

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_attempts = 0

    def record_success(self):
        """Record successful request"""
        if self.state == CircuitBreakerState.HALF_OPEN:
            logger.info("Circuit breaker recovery successful, closing circuit")
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.half_open_attempts = 0
        elif self.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.half_open_attempts += 1
            if self.half_open_attempts >= self.half_open_max_attempts:
                logger.warning("Circuit breaker half-open test failed, reopening circuit")
                self.state = CircuitBreakerState.OPEN
                self.half_open_attempts = 0
        elif self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit breaker threshold reached ({self.failure_count} failures), "
                    "opening circuit"
                )
                self.state = CircuitBreakerState.OPEN

    def can_attempt(self) -> bool:
        """Check if request can be attempted"""
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout_seconds:
                    logger.info("Circuit breaker recovery timeout elapsed, entering half-open state")
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_attempts = 0
                    return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            return True

        return False

    def get_state(self) -> CircuitBreakerState:
        """Get current circuit breaker state"""
        return self.state


class EngineClient:
    """Base client for AI detection engines"""

    def __init__(
        self,
        engine_type: DetectionType,
        endpoint: str,
        timeout_seconds: int = 5,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.engine_type = engine_type
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.model_version = "v1.0.0"  # Default version
        self.healthy = True
        self.last_health_check: Optional[datetime] = None

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def predict(
        self, photo_url: str, metadata: Optional[Dict] = None
    ) -> EngineResult:
        """
        Send prediction request to engine with retry logic.

        Args:
            photo_url: URL of the photo to process
            metadata: Additional metadata for the request

        Returns:
            EngineResult with predictions

        Raises:
            Exception: If circuit breaker is open or request fails
        """
        if not self.circuit_breaker.can_attempt():
            state = self.circuit_breaker.get_state()
            error_msg = f"Circuit breaker is {state.value} for {self.engine_type.value} engine"
            logger.error(error_msg)
            metrics_collector.record_circuit_breaker_failure(self.engine_type.value)
            raise Exception(error_msg)

        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.endpoint}/predict",
                    json={
                        "photo_url": photo_url,
                        "metadata": metadata or {},
                        "model_version": self.model_version,
                    },
                )
                response.raise_for_status()
                result_data = response.json()

            processing_time_ms = int((time.time() - start_time) * 1000)

            # Create engine result
            engine_result = EngineResult(
                engine_type=self.engine_type,
                model_version=result_data.get("model_version", self.model_version),
                confidence=result_data.get("confidence", 0.0),
                results=result_data.get("results", {}),
                processing_time_ms=processing_time_ms,
            )

            # Record success
            self.circuit_breaker.record_success()
            metrics_collector.record_engine_request(
                engine_type=self.engine_type.value,
                status="success",
                duration_seconds=time.time() - start_time,
                confidence=engine_result.confidence,
                model_version=engine_result.model_version,
                endpoint=self.endpoint,
            )

            # Update circuit breaker state metric
            metrics_collector.record_circuit_breaker_state(
                self.engine_type.value,
                self.circuit_breaker.get_state().value
            )

            return engine_result

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Engine {self.engine_type.value} prediction failed: {str(e)}"
            logger.error(error_msg)

            # Record failure
            self.circuit_breaker.record_failure()
            metrics_collector.record_engine_request(
                engine_type=self.engine_type.value,
                status="failed",
                duration_seconds=time.time() - start_time,
                endpoint=self.endpoint,
            )

            # Update circuit breaker state metric
            metrics_collector.record_circuit_breaker_state(
                self.engine_type.value,
                self.circuit_breaker.get_state().value
            )

            return EngineResult(
                engine_type=self.engine_type,
                model_version=self.model_version,
                confidence=0.0,
                results={},
                processing_time_ms=processing_time_ms,
                error=error_msg,
            )

    async def health_check(self) -> EngineHealth:
        """
        Check engine health status.

        Returns:
            EngineHealth with current status
        """
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.endpoint}/health")
                response.raise_for_status()

            response_time_ms = int((time.time() - start_time) * 1000)
            self.healthy = True
            self.last_health_check = datetime.utcnow()

            metrics_collector.record_health_check(
                engine_type=self.engine_type.value,
                endpoint=self.endpoint,
                is_healthy=True,
                duration_seconds=time.time() - start_time,
            )

            return EngineHealth(
                engine_type=self.engine_type,
                endpoint=self.endpoint,
                healthy=True,
                last_check=self.last_health_check,
                response_time_ms=response_time_ms,
                error_count=self.circuit_breaker.failure_count,
                consecutive_failures=self.circuit_breaker.failure_count,
            )

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            self.healthy = False
            self.last_health_check = datetime.utcnow()

            metrics_collector.record_health_check(
                engine_type=self.engine_type.value,
                endpoint=self.endpoint,
                is_healthy=False,
                duration_seconds=time.time() - start_time,
            )

            logger.error(f"Health check failed for {self.engine_type.value}: {e}")
            return EngineHealth(
                engine_type=self.engine_type,
                endpoint=self.endpoint,
                healthy=False,
                last_check=self.last_health_check,
                response_time_ms=response_time_ms,
                error_count=self.circuit_breaker.failure_count + 1,
                consecutive_failures=self.circuit_breaker.failure_count + 1,
            )


class LoadBalancedEngineClient:
    """Load-balanced client managing multiple engine endpoints"""

    def __init__(self, engine_type: DetectionType, endpoints: List[str]):
        self.engine_type = engine_type
        self.clients = [
            EngineClient(engine_type, endpoint)
            for endpoint in endpoints
        ]
        self.current_index = 0

    def _get_next_client(self) -> Optional[EngineClient]:
        """Get next available client using round-robin"""
        if not self.clients:
            return None

        # Try each client in round-robin fashion
        attempts = 0
        while attempts < len(self.clients):
            client = self.clients[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.clients)

            # Check if circuit breaker allows attempt
            if client.circuit_breaker.can_attempt():
                return client

            attempts += 1

        # All clients have open circuit breakers
        logger.error(f"All endpoints for {self.engine_type.value} are unavailable")
        return None

    async def predict(
        self, photo_url: str, metadata: Optional[Dict] = None
    ) -> EngineResult:
        """
        Send prediction request with load balancing.

        Args:
            photo_url: URL of the photo to process
            metadata: Additional metadata

        Returns:
            EngineResult from an available endpoint

        Raises:
            Exception: If no endpoints are available
        """
        client = self._get_next_client()
        if not client:
            raise Exception(
                f"No available endpoints for {self.engine_type.value} engine"
            )

        return await client.predict(photo_url, metadata)

    async def health_check_all(self) -> List[EngineHealth]:
        """
        Check health of all endpoints.

        Returns:
            List of EngineHealth for all endpoints
        """
        tasks = [client.health_check() for client in self.clients]
        return await asyncio.gather(*tasks)
