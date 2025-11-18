"""Unit tests for AI Orchestrator API routes"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from fastapi.testclient import TestClient

from src.main import app
from src.schemas.orchestrator import (
    DetectionRequest,
    DetectionResponse,
    DetectionType,
    DetectionStatus,
    Priority,
    EngineResult,
    OrchestratorMetrics,
)


class TestOrchestratorAPI:
    """Tests for Orchestrator API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        # Create a test token
        from src.services.auth_service import create_access_token
        token = create_access_token(user_id=uuid4())
        return {"Authorization": f"Bearer {token}"}

    def test_create_detection_request_unauthorized(self, client):
        """Test detection request without authentication"""
        request_data = {
            "photo_id": str(uuid4()),
            "photo_url": "s3://bucket/photo.jpg",
            "detection_types": ["damage"],
            "priority": "normal",
        }

        response = client.post(
            "/api/v1/orchestrator/detect",
            json=request_data
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_detection_request_success(self, client, auth_headers):
        """Test successful detection request"""
        photo_id = uuid4()
        request_data = {
            "photo_id": str(photo_id),
            "photo_url": "s3://bucket/photo.jpg",
            "detection_types": ["damage"],
            "priority": "normal",
            "metadata": {},
        }

        mock_response = DetectionResponse(
            request_id=uuid4(),
            detection_id=uuid4(),
            photo_id=photo_id,
            status=DetectionStatus.COMPLETED,
            results={
                "damage": EngineResult(
                    engine_type=DetectionType.DAMAGE,
                    model_version="v1.2.0",
                    confidence=0.85,
                    results={},
                    processing_time_ms=250,
                )
            },
            processing_time_ms=300,
        )

        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'process_detection_request',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            response = client.post(
                "/api/v1/orchestrator/detect",
                json=request_data,
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["photo_id"] == str(photo_id)

    def test_create_detection_request_invalid_data(self, client, auth_headers):
        """Test detection request with invalid data"""
        request_data = {
            "photo_id": "invalid-uuid",
            "photo_url": "",  # Empty URL
            "detection_types": ["invalid_type"],
        }

        response = client.post(
            "/api/v1/orchestrator/detect",
            json=request_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_create_detection_request_with_correlation_id(self, client, auth_headers):
        """Test detection request with correlation ID header"""
        photo_id = uuid4()
        correlation_id = "test-correlation-123"

        request_data = {
            "photo_id": str(photo_id),
            "photo_url": "s3://bucket/photo.jpg",
            "detection_types": ["damage"],
        }

        mock_response = DetectionResponse(
            request_id=uuid4(),
            detection_id=uuid4(),
            photo_id=photo_id,
            status=DetectionStatus.COMPLETED,
            correlation_id=correlation_id,
        )

        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'process_detection_request',
            new_callable=AsyncMock,
            return_value=mock_response
        ):
            headers = {**auth_headers, "X-Correlation-ID": correlation_id}
            response = client.post(
                "/api/v1/orchestrator/detect",
                json=request_data,
                headers=headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["correlation_id"] == correlation_id

    @pytest.mark.asyncio
    async def test_get_orchestrator_health(self, client):
        """Test health check endpoint"""
        mock_health = {
            "status": "healthy",
            "total_engines": 3,
            "healthy_engines": 3,
            "engines": [],
        }

        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'get_health_status',
            new_callable=AsyncMock,
            return_value=mock_health
        ):
            response = client.get("/api/v1/orchestrator/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["total_engines"] == 3

    @pytest.mark.asyncio
    async def test_get_orchestrator_health_degraded(self, client):
        """Test health check with degraded status"""
        mock_health = {
            "status": "degraded",
            "total_engines": 3,
            "healthy_engines": 2,
            "engines": [],
        }

        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'get_health_status',
            new_callable=AsyncMock,
            return_value=mock_health
        ):
            response = client.get("/api/v1/orchestrator/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"

    @pytest.mark.asyncio
    async def test_get_orchestrator_health_error(self, client):
        """Test health check endpoint with error"""
        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'get_health_status',
            new_callable=AsyncMock,
            side_effect=Exception("Health check failed")
        ):
            response = client.get("/api/v1/orchestrator/health")

            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"

    def test_get_orchestrator_metrics(self, client, auth_headers):
        """Test metrics endpoint"""
        mock_metrics = OrchestratorMetrics(
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            avg_processing_time_ms=350.5,
            p50_latency_ms=300.0,
            p90_latency_ms=500.0,
            p95_latency_ms=600.0,
            error_rate=0.05,
        )

        from src.api.orchestrator import orchestrator

        with patch.object(
            orchestrator,
            'get_metrics',
            return_value=mock_metrics
        ):
            response = client.get(
                "/api/v1/orchestrator/metrics",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_requests"] == 100
            assert data["successful_requests"] == 95
            assert data["error_rate"] == 0.05

    def test_get_detection_status(self, client, auth_headers):
        """Test getting detection status by request ID"""
        request_id = uuid4()
        photo_id = uuid4()

        mock_response = DetectionResponse(
            request_id=request_id,
            detection_id=uuid4(),
            photo_id=photo_id,
            status=DetectionStatus.COMPLETED,
        )

        from src.api.orchestrator import orchestrator
        orchestrator.request_history = [mock_response]

        response = client.get(
            f"/api/v1/orchestrator/status/{request_id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == str(request_id)
        assert data["status"] == "completed"

    def test_get_detection_status_not_found(self, client, auth_headers):
        """Test getting status for non-existent request"""
        request_id = uuid4()

        from src.api.orchestrator import orchestrator
        orchestrator.request_history = []

        response = client.get(
            f"/api/v1/orchestrator/status/{request_id}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_get_available_models(self, client, auth_headers):
        """Test getting available models"""
        response = client.get(
            "/api/v1/orchestrator/models",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should have models for each detection type
        assert "damage" in data
        assert "material" in data
        assert "volume" in data

        # Check model structure
        damage_models = data["damage"]
        assert len(damage_models) > 0
        assert "name" in damage_models[0]
        assert "version" in damage_models[0]
        assert "endpoint" in damage_models[0]

    def test_get_available_models_unauthorized(self, client):
        """Test getting models without authentication"""
        response = client.get("/api/v1/orchestrator/models")

        assert response.status_code == 401
