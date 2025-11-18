"""Unit tests for AI Orchestrator service"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4
from datetime import datetime

from src.services.ai_orchestrator import AIOrchestrator, ModelRegistry
from src.schemas.orchestrator import (
    DetectionRequest,
    DetectionResponse,
    DetectionType,
    DetectionStatus,
    Priority,
    ModelVersion,
    ABTestConfig,
    EngineResult,
)


class TestModelRegistry:
    """Tests for ModelRegistry"""

    def test_model_registry_initialization(self):
        """Test model registry initializes with default models"""
        registry = ModelRegistry()

        assert DetectionType.DAMAGE in registry.models
        assert DetectionType.MATERIAL in registry.models
        assert DetectionType.VOLUME in registry.models

        # Check damage model
        damage_models = registry.models[DetectionType.DAMAGE]
        assert len(damage_models) > 0
        assert damage_models[0].version == "v1.2.0"

    def test_get_active_model(self):
        """Test getting active model for detection type"""
        registry = ModelRegistry()

        damage_model = registry.get_active_model(DetectionType.DAMAGE)
        assert damage_model is not None
        assert damage_model.engine_type == DetectionType.DAMAGE
        assert damage_model.enabled is True

    def test_register_model(self):
        """Test registering new model version"""
        registry = ModelRegistry()

        new_model = ModelVersion(
            name="damage-detector",
            version="v2.0.0",
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-engine-v2:8001",
            confidence_threshold=0.85,
            enabled=True,
        )

        initial_count = len(registry.models[DetectionType.DAMAGE])
        registry.register_model(new_model)

        assert len(registry.models[DetectionType.DAMAGE]) == initial_count + 1

    def test_create_ab_test(self):
        """Test creating A/B test configuration"""
        registry = ModelRegistry()

        model_a = ModelVersion(
            name="damage-detector",
            version="v1.0.0",
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-v1:8001",
        )

        model_b = ModelVersion(
            name="damage-detector",
            version="v2.0.0",
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-v2:8001",
        )

        ab_config = ABTestConfig(
            experiment_id="damage-v1-vs-v2",
            model_a=model_a,
            model_b=model_b,
            traffic_split=0.5,
            enabled=True,
        )

        registry.create_ab_test(ab_config)
        assert "damage-v1-vs-v2" in registry.ab_tests

    def test_get_model_for_request_with_ab_test(self):
        """Test model selection with A/B testing"""
        registry = ModelRegistry()

        model_a = ModelVersion(
            name="damage-detector",
            version="v1.0.0",
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-v1:8001",
        )

        model_b = ModelVersion(
            name="damage-detector",
            version="v2.0.0",
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-v2:8001",
        )

        ab_config = ABTestConfig(
            experiment_id="test-exp",
            model_a=model_a,
            model_b=model_b,
            traffic_split=0.5,
            enabled=True,
        )

        registry.create_ab_test(ab_config)

        # Test deterministic selection
        request_id_1 = "request-1"
        request_id_2 = "request-2"

        model_1 = registry.get_model_for_request(DetectionType.DAMAGE, request_id_1)
        model_2 = registry.get_model_for_request(DetectionType.DAMAGE, request_id_2)

        # Should consistently return same model for same request ID
        assert model_1 in [model_a, model_b]
        assert model_2 in [model_a, model_b]

        # Verify consistency
        assert registry.get_model_for_request(DetectionType.DAMAGE, request_id_1) == model_1


class TestAIOrchestrator:
    """Tests for AIOrchestrator service"""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing"""
        return AIOrchestrator()

    @pytest.mark.asyncio
    async def test_process_detection_request_success(self, orchestrator):
        """Test successful detection request processing"""
        request = DetectionRequest(
            photo_id=uuid4(),
            photo_url="s3://bucket/photo.jpg",
            detection_types=[DetectionType.DAMAGE],
            priority=Priority.NORMAL,
            metadata={"project_id": str(uuid4())},
        )

        # Mock the engine client
        mock_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.2.0",
            confidence=0.85,
            results={"detections": [{"type": "hail_damage", "confidence": 0.85}]},
            processing_time_ms=250,
        )

        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'predict',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = await orchestrator.process_detection_request(request)

            assert response.status == DetectionStatus.COMPLETED
            assert response.photo_id == request.photo_id
            assert DetectionType.DAMAGE.value in response.results
            assert response.results[DetectionType.DAMAGE.value].confidence == 0.85
            assert response.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_process_detection_request_multiple_types(self, orchestrator):
        """Test detection request with multiple detection types"""
        request = DetectionRequest(
            photo_id=uuid4(),
            photo_url="s3://bucket/photo.jpg",
            detection_types=[DetectionType.DAMAGE, DetectionType.MATERIAL],
            priority=Priority.HIGH,
        )

        # Mock results for both engines
        damage_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.2.0",
            confidence=0.85,
            results={"detections": []},
            processing_time_ms=250,
        )

        material_result = EngineResult(
            engine_type=DetectionType.MATERIAL,
            model_version="v1.1.0",
            confidence=0.90,
            results={"materials": []},
            processing_time_ms=300,
        )

        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'predict',
            new_callable=AsyncMock,
            return_value=damage_result
        ), patch.object(
            orchestrator.engine_clients[DetectionType.MATERIAL],
            'predict',
            new_callable=AsyncMock,
            return_value=material_result
        ):
            response = await orchestrator.process_detection_request(request)

            assert response.status == DetectionStatus.COMPLETED
            assert len(response.results) == 2
            assert DetectionType.DAMAGE.value in response.results
            assert DetectionType.MATERIAL.value in response.results

    @pytest.mark.asyncio
    async def test_process_detection_request_partial_failure(self, orchestrator):
        """Test detection request with partial failure"""
        request = DetectionRequest(
            photo_id=uuid4(),
            photo_url="s3://bucket/photo.jpg",
            detection_types=[DetectionType.DAMAGE, DetectionType.MATERIAL],
        )

        # One success, one failure
        damage_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.2.0",
            confidence=0.85,
            results={"detections": []},
            processing_time_ms=250,
        )

        material_result = EngineResult(
            engine_type=DetectionType.MATERIAL,
            model_version="v1.1.0",
            confidence=0.0,
            results={},
            processing_time_ms=100,
            error="Engine timeout",
        )

        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'predict',
            new_callable=AsyncMock,
            return_value=damage_result
        ), patch.object(
            orchestrator.engine_clients[DetectionType.MATERIAL],
            'predict',
            new_callable=AsyncMock,
            return_value=material_result
        ):
            response = await orchestrator.process_detection_request(request)

            assert response.status == DetectionStatus.PARTIAL
            assert len(response.results) == 2
            assert response.results[DetectionType.MATERIAL.value].error is not None

    @pytest.mark.asyncio
    async def test_process_detection_request_complete_failure(self, orchestrator):
        """Test detection request with complete failure"""
        request = DetectionRequest(
            photo_id=uuid4(),
            photo_url="s3://bucket/photo.jpg",
            detection_types=[DetectionType.DAMAGE],
        )

        # Mock engine failure
        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'predict',
            new_callable=AsyncMock,
            side_effect=Exception("Engine unavailable")
        ):
            response = await orchestrator.process_detection_request(request)

            assert response.status == DetectionStatus.FAILED
            assert response.error is not None

    @pytest.mark.asyncio
    async def test_get_health_status(self, orchestrator):
        """Test health status retrieval"""
        from src.schemas.orchestrator import EngineHealth

        mock_health = EngineHealth(
            engine_type=DetectionType.DAMAGE,
            endpoint="http://damage-engine:8001",
            healthy=True,
            last_check=datetime.utcnow(),
            response_time_ms=50,
        )

        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'health_check_all',
            new_callable=AsyncMock,
            return_value=[mock_health]
        ):
            health = await orchestrator.get_health_status()

            assert health["status"] == "healthy"
            assert health["total_engines"] >= 1
            assert health["healthy_engines"] >= 1

    def test_get_metrics(self, orchestrator):
        """Test metrics retrieval"""
        # Add some test data to history
        test_response = DetectionResponse(
            request_id=uuid4(),
            detection_id=uuid4(),
            photo_id=uuid4(),
            status=DetectionStatus.COMPLETED,
            processing_time_ms=500,
        )

        orchestrator.request_history.append(test_response)

        metrics = orchestrator.get_metrics()

        assert metrics.total_requests >= 1
        assert metrics.successful_requests >= 1
        assert metrics.avg_processing_time_ms > 0

    def test_add_to_history_with_size_limit(self, orchestrator):
        """Test history size limiting"""
        orchestrator.max_history_size = 10

        # Add more than max size
        for i in range(15):
            response = DetectionResponse(
                request_id=uuid4(),
                detection_id=uuid4(),
                photo_id=uuid4(),
                status=DetectionStatus.COMPLETED,
                processing_time_ms=100,
            )
            orchestrator._add_to_history(response)

        # Should be limited to max size
        assert len(orchestrator.request_history) == 10

    @pytest.mark.asyncio
    async def test_correlation_id_propagation(self, orchestrator):
        """Test correlation ID is properly propagated"""
        request = DetectionRequest(
            photo_id=uuid4(),
            photo_url="s3://bucket/photo.jpg",
            detection_types=[DetectionType.DAMAGE],
        )

        correlation_id = "test-correlation-123"

        mock_result = EngineResult(
            engine_type=DetectionType.DAMAGE,
            model_version="v1.2.0",
            confidence=0.85,
            results={},
            processing_time_ms=250,
        )

        with patch.object(
            orchestrator.engine_clients[DetectionType.DAMAGE],
            'predict',
            new_callable=AsyncMock,
            return_value=mock_result
        ):
            response = await orchestrator.process_detection_request(
                request, correlation_id=correlation_id
            )

            assert response.correlation_id == correlation_id
