"""AI Orchestrator service for managing detection requests and coordinating AI inference"""

import asyncio
import logging
import time
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict

from src.schemas.orchestrator import (
    DetectionRequest,
    DetectionResponse,
    DetectionType,
    DetectionStatus,
    EngineResult,
    ModelVersion,
    ABTestConfig,
    LoadBalancerConfig,
    OrchestratorMetrics,
)
from src.services.engine_clients import EngineClient, LoadBalancedEngineClient
from src.monitoring.metrics import metrics_collector
from src.config import settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing model versions and A/B testing"""

    def __init__(self):
        self.models: Dict[DetectionType, List[ModelVersion]] = defaultdict(list)
        self.ab_tests: Dict[str, ABTestConfig] = {}
        self._initialize_default_models()

    def _initialize_default_models(self):
        """Initialize default model versions"""
        # Damage detection models
        self.models[DetectionType.DAMAGE] = [
            ModelVersion(
                name="damage-detector",
                version="v1.2.0",
                engine_type=DetectionType.DAMAGE,
                endpoint="http://damage-engine:8001",
                confidence_threshold=0.75,
                enabled=True,
            )
        ]

        # Material detection models
        self.models[DetectionType.MATERIAL] = [
            ModelVersion(
                name="material-detector",
                version="v1.1.0",
                engine_type=DetectionType.MATERIAL,
                endpoint="http://material-engine:8002",
                confidence_threshold=0.75,
                enabled=True,
            )
        ]

        # Volume estimation models
        self.models[DetectionType.VOLUME] = [
            ModelVersion(
                name="volume-estimator",
                version="v1.0.0",
                engine_type=DetectionType.VOLUME,
                endpoint="http://volume-engine:8003",
                confidence_threshold=0.70,
                enabled=True,
            )
        ]

    def get_active_model(self, detection_type: DetectionType) -> Optional[ModelVersion]:
        """
        Get the active model version for a detection type.

        Args:
            detection_type: Type of detection

        Returns:
            Active ModelVersion or None
        """
        models = self.models.get(detection_type, [])
        active_models = [m for m in models if m.enabled]

        if not active_models:
            logger.warning(f"No active models for {detection_type.value}")
            return None

        # Return the latest version (assumes sorted by version)
        return active_models[-1]

    def register_model(self, model: ModelVersion):
        """Register a new model version"""
        self.models[model.engine_type].append(model)
        logger.info(f"Registered model {model.name} v{model.version} for {model.engine_type.value}")

    def create_ab_test(self, config: ABTestConfig):
        """Create A/B test configuration"""
        self.ab_tests[config.experiment_id] = config
        logger.info(f"Created A/B test {config.experiment_id}")

    def get_model_for_request(
        self, detection_type: DetectionType, request_id: str
    ) -> Optional[ModelVersion]:
        """
        Get model version for request, considering A/B tests.

        Args:
            detection_type: Type of detection
            request_id: Request ID for deterministic A/B split

        Returns:
            ModelVersion to use
        """
        # Check for active A/B tests
        for test in self.ab_tests.values():
            if not test.enabled:
                continue

            if test.model_a.engine_type == detection_type:
                # Use request_id hash for deterministic split
                hash_value = hash(request_id) % 100
                use_model_a = hash_value < (test.traffic_split * 100)
                return test.model_a if use_model_a else test.model_b

        # No A/B test, return active model
        return self.get_active_model(detection_type)


class AIOrchestrator:
    """Main orchestrator service for coordinating AI detection across multiple engines"""

    def __init__(self, config: Optional[LoadBalancerConfig] = None):
        self.config = config or LoadBalancerConfig()
        self.model_registry = ModelRegistry()
        self.engine_clients: Dict[DetectionType, LoadBalancedEngineClient] = {}
        self.request_history: List[DetectionResponse] = []
        self.max_history_size = 1000
        self._initialize_engine_clients()

    def _initialize_engine_clients(self):
        """Initialize engine clients for each detection type"""
        # Initialize clients with endpoints from model registry
        for detection_type in DetectionType:
            model = self.model_registry.get_active_model(detection_type)
            if model and model.endpoint:
                # For now, use single endpoint; can be extended to multiple
                self.engine_clients[detection_type] = LoadBalancedEngineClient(
                    engine_type=detection_type,
                    endpoints=[model.endpoint]
                )
                logger.info(f"Initialized {detection_type.value} engine client")

    async def process_detection_request(
        self, request: DetectionRequest, correlation_id: Optional[str] = None
    ) -> DetectionResponse:
        """
        Process a detection request by routing to appropriate engines.

        Args:
            request: DetectionRequest with photo and detection types
            correlation_id: Optional correlation ID for distributed tracing

        Returns:
            DetectionResponse with aggregated results
        """
        start_time = time.time()
        request_id = str(uuid.uuid4())

        if correlation_id is None:
            correlation_id = f"orch-{request_id}"

        logger.info(
            f"Processing detection request {request_id} for photo {request.photo_id} "
            f"with types {request.detection_types} (correlation: {correlation_id})"
        )

        # Initialize response
        response = DetectionResponse(
            request_id=uuid.UUID(request_id),
            detection_id=uuid.uuid4(),
            photo_id=request.photo_id,
            status=DetectionStatus.PROCESSING,
            correlation_id=correlation_id,
        )

        # Route to engines based on detection types
        tasks = []
        for detection_type in request.detection_types:
            task = self._route_to_engine(
                detection_type=detection_type,
                photo_url=request.photo_url,
                metadata=request.metadata,
                request_id=request_id,
            )
            tasks.append(task)

        # Execute all engine requests in parallel
        try:
            engine_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            successful_count = 0
            failed_count = 0

            for i, result in enumerate(engine_results):
                detection_type = request.detection_types[i]

                if isinstance(result, Exception):
                    logger.error(f"Engine {detection_type.value} failed: {result}")
                    response.results[detection_type.value] = EngineResult(
                        engine_type=detection_type,
                        model_version="unknown",
                        confidence=0.0,
                        results={},
                        processing_time_ms=0,
                        error=str(result),
                    )
                    failed_count += 1
                else:
                    response.results[detection_type.value] = result
                    response.model_versions[detection_type.value] = result.model_version

                    if result.error:
                        failed_count += 1
                    else:
                        successful_count += 1

            # Determine final status
            if successful_count == len(request.detection_types):
                response.status = DetectionStatus.COMPLETED
            elif successful_count > 0:
                response.status = DetectionStatus.PARTIAL
            else:
                response.status = DetectionStatus.FAILED
                response.error = "All detection engines failed"

        except Exception as e:
            logger.error(f"Error processing detection request {request_id}: {e}")
            response.status = DetectionStatus.FAILED
            response.error = str(e)

        # Calculate total processing time
        processing_time_ms = int((time.time() - start_time) * 1000)
        response.processing_time_ms = processing_time_ms
        response.timestamp = datetime.utcnow()

        # Record metrics
        for detection_type in request.detection_types:
            metrics_collector.record_request(
                detection_type=detection_type.value,
                priority=request.priority.value,
                status=response.status.value,
                duration_seconds=processing_time_ms / 1000.0,
            )

        # Store in history
        self._add_to_history(response)

        logger.info(
            f"Completed detection request {request_id} with status {response.status.value} "
            f"in {processing_time_ms}ms"
        )

        return response

    async def _route_to_engine(
        self,
        detection_type: DetectionType,
        photo_url: str,
        metadata: Dict,
        request_id: str,
    ) -> EngineResult:
        """
        Route request to specific detection engine.

        Args:
            detection_type: Type of detection to perform
            photo_url: URL of photo to process
            metadata: Additional metadata
            request_id: Request ID for tracking

        Returns:
            EngineResult from the detection engine
        """
        # Get appropriate model version (considers A/B testing)
        model = self.model_registry.get_model_for_request(detection_type, request_id)
        if not model:
            error_msg = f"No model available for {detection_type.value}"
            logger.error(error_msg)
            return EngineResult(
                engine_type=detection_type,
                model_version="unavailable",
                confidence=0.0,
                results={},
                processing_time_ms=0,
                error=error_msg,
            )

        # Get load-balanced client
        client = self.engine_clients.get(detection_type)
        if not client:
            error_msg = f"No client configured for {detection_type.value}"
            logger.error(error_msg)
            return EngineResult(
                engine_type=detection_type,
                model_version=model.version,
                confidence=0.0,
                results={},
                processing_time_ms=0,
                error=error_msg,
            )

        # Make prediction request
        logger.debug(f"Routing {detection_type.value} request to {model.endpoint}")
        return await client.predict(photo_url, metadata)

    def _add_to_history(self, response: DetectionResponse):
        """Add response to history with size limit"""
        self.request_history.append(response)
        if len(self.request_history) > self.max_history_size:
            self.request_history.pop(0)

    async def get_health_status(self) -> Dict[str, any]:
        """
        Get health status of all engines.

        Returns:
            Dictionary with health information
        """
        health_checks = []
        for detection_type, client in self.engine_clients.items():
            checks = await client.health_check_all()
            health_checks.extend(checks)

        # Summarize health
        total_engines = len(health_checks)
        healthy_engines = sum(1 for h in health_checks if h.healthy)

        return {
            "status": "healthy" if healthy_engines == total_engines else "degraded",
            "total_engines": total_engines,
            "healthy_engines": healthy_engines,
            "engines": [
                {
                    "type": h.engine_type.value,
                    "endpoint": h.endpoint,
                    "healthy": h.healthy,
                    "response_time_ms": h.response_time_ms,
                    "error_count": h.error_count,
                    "last_check": h.last_check.isoformat() if h.last_check else None,
                }
                for h in health_checks
            ],
        }

    def get_metrics(self) -> OrchestratorMetrics:
        """
        Get orchestrator metrics.

        Returns:
            OrchestratorMetrics with current statistics
        """
        if not self.request_history:
            return OrchestratorMetrics()

        total = len(self.request_history)
        successful = sum(1 for r in self.request_history if r.status == DetectionStatus.COMPLETED)
        failed = sum(1 for r in self.request_history if r.status == DetectionStatus.FAILED)

        processing_times = [r.processing_time_ms for r in self.request_history]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0

        # Calculate percentiles
        sorted_times = sorted(processing_times)
        n = len(sorted_times)

        def percentile(p: float) -> float:
            if not sorted_times:
                return 0.0
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            return sorted_times[f] + (k - f) * (sorted_times[c] - sorted_times[f])

        # Engine-specific metrics
        engine_metrics = {}
        for detection_type in DetectionType:
            type_results = []
            for response in self.request_history:
                if detection_type.value in response.results:
                    type_results.append(response.results[detection_type.value])

            if type_results:
                engine_metrics[detection_type.value] = {
                    "total_requests": len(type_results),
                    "avg_confidence": sum(r.confidence for r in type_results) / len(type_results),
                    "error_count": sum(1 for r in type_results if r.error),
                }

        return OrchestratorMetrics(
            total_requests=total,
            successful_requests=successful,
            failed_requests=failed,
            avg_processing_time_ms=avg_time,
            p50_latency_ms=percentile(0.50),
            p90_latency_ms=percentile(0.90),
            p95_latency_ms=percentile(0.95),
            error_rate=failed / total if total > 0 else 0.0,
            engine_metrics=engine_metrics,
        )
