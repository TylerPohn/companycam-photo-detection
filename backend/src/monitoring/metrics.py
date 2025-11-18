"""Prometheus metrics for AI Orchestrator service"""

import time
import logging
from typing import Dict, List
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, Info
from src.schemas.orchestrator import DetectionType

logger = logging.getLogger(__name__)


# Request metrics
orchestrator_requests_total = Counter(
    'orchestrator_requests_total',
    'Total number of orchestrator requests',
    ['detection_type', 'priority', 'status']
)

orchestrator_request_duration_seconds = Histogram(
    'orchestrator_request_duration_seconds',
    'Time spent processing orchestrator requests',
    ['detection_type', 'status'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)

# Engine metrics
engine_requests_total = Counter(
    'engine_requests_total',
    'Total number of engine requests',
    ['engine_type', 'status']
)

engine_request_duration_seconds = Histogram(
    'engine_request_duration_seconds',
    'Time spent on engine requests',
    ['engine_type'],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

engine_confidence_score = Histogram(
    'engine_confidence_score',
    'Distribution of engine confidence scores',
    ['engine_type'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Circuit breaker metrics
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['engine_type']
)

circuit_breaker_failures = Counter(
    'circuit_breaker_failures_total',
    'Total number of circuit breaker failures',
    ['engine_type']
)

# Load balancing metrics
load_balancer_endpoint_requests = Counter(
    'load_balancer_endpoint_requests_total',
    'Total requests per endpoint',
    ['engine_type', 'endpoint', 'status']
)

# Model version metrics
model_version_requests = Counter(
    'model_version_requests_total',
    'Requests per model version',
    ['engine_type', 'model_version']
)

# Health check metrics
health_check_status = Gauge(
    'health_check_status',
    'Health check status (1=healthy, 0=unhealthy)',
    ['engine_type', 'endpoint']
)

health_check_duration_seconds = Histogram(
    'health_check_duration_seconds',
    'Health check response time',
    ['engine_type', 'endpoint']
)

# Damage Detection specific metrics
damage_detections_total = Counter(
    'damage_detections_total',
    'Total number of damage detections',
    ['damage_type', 'severity']
)

damage_inference_duration_seconds = Histogram(
    'damage_inference_duration_seconds',
    'Time spent on damage detection inference',
    ['model_component'],
    buckets=[0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.75, 1.0, 2.0]
)

damage_confidence_distribution = Histogram(
    'damage_confidence_distribution',
    'Distribution of damage detection confidence scores',
    ['damage_type'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

damage_area_percentage = Histogram(
    'damage_area_percentage',
    'Distribution of damage area percentages',
    ['damage_type'],
    buckets=[0, 1, 2, 5, 10, 15, 20, 30, 40, 50, 75, 100]
)

segmentation_masks_generated = Counter(
    'segmentation_masks_generated_total',
    'Total number of segmentation masks generated',
    ['status']
)


class MetricsCollector:
    """Collector for orchestrator metrics with in-memory statistics"""

    def __init__(self):
        self.latencies: Dict[str, List[float]] = defaultdict(list)
        self.max_latency_samples = 1000  # Keep last N samples for percentile calculation

    def record_request(
        self,
        detection_type: str,
        priority: str,
        status: str,
        duration_seconds: float
    ):
        """Record an orchestrator request"""
        orchestrator_requests_total.labels(
            detection_type=detection_type,
            priority=priority,
            status=status
        ).inc()

        orchestrator_request_duration_seconds.labels(
            detection_type=detection_type,
            status=status
        ).observe(duration_seconds)

        # Store latency for percentile calculation
        key = f"{detection_type}_{status}"
        self.latencies[key].append(duration_seconds * 1000)  # Convert to ms
        if len(self.latencies[key]) > self.max_latency_samples:
            self.latencies[key].pop(0)

    def record_engine_request(
        self,
        engine_type: str,
        status: str,
        duration_seconds: float,
        confidence: float = None,
        model_version: str = None,
        endpoint: str = None
    ):
        """Record an engine request"""
        engine_requests_total.labels(
            engine_type=engine_type,
            status=status
        ).inc()

        engine_request_duration_seconds.labels(
            engine_type=engine_type
        ).observe(duration_seconds)

        if confidence is not None:
            engine_confidence_score.labels(
                engine_type=engine_type
            ).observe(confidence)

        if model_version:
            model_version_requests.labels(
                engine_type=engine_type,
                model_version=model_version
            ).inc()

        if endpoint:
            load_balancer_endpoint_requests.labels(
                engine_type=engine_type,
                endpoint=endpoint,
                status=status
            ).inc()

    def record_circuit_breaker_state(self, engine_type: str, state: str):
        """Record circuit breaker state"""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        circuit_breaker_state.labels(engine_type=engine_type).set(state_value)

    def record_circuit_breaker_failure(self, engine_type: str):
        """Record circuit breaker failure"""
        circuit_breaker_failures.labels(engine_type=engine_type).inc()

    def record_health_check(
        self,
        engine_type: str,
        endpoint: str,
        is_healthy: bool,
        duration_seconds: float = None
    ):
        """Record health check result"""
        health_check_status.labels(
            engine_type=engine_type,
            endpoint=endpoint
        ).set(1 if is_healthy else 0)

        if duration_seconds is not None:
            health_check_duration_seconds.labels(
                engine_type=engine_type,
                endpoint=endpoint
            ).observe(duration_seconds)

    def get_latency_percentiles(self, detection_type: str, status: str = "completed") -> Dict[str, float]:
        """Calculate latency percentiles from stored samples"""
        key = f"{detection_type}_{status}"
        latencies = self.latencies.get(key, [])

        if not latencies:
            return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        def percentile(p: float) -> float:
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            return sorted_latencies[f] + (k - f) * (sorted_latencies[c] - sorted_latencies[f])

        return {
            "p50": percentile(0.50),
            "p90": percentile(0.90),
            "p95": percentile(0.95),
            "p99": percentile(0.99),
        }

    def record_damage_detection(
        self,
        damage_type: str,
        severity: str,
        confidence: float,
        area_percentage: float
    ):
        """Record a damage detection"""
        damage_detections_total.labels(
            damage_type=damage_type,
            severity=severity
        ).inc()

        damage_confidence_distribution.labels(
            damage_type=damage_type
        ).observe(confidence)

        damage_area_percentage.labels(
            damage_type=damage_type
        ).observe(area_percentage)

    def record_damage_inference(self, model_component: str, duration_seconds: float):
        """Record damage inference timing"""
        damage_inference_duration_seconds.labels(
            model_component=model_component
        ).observe(duration_seconds)

    def record_segmentation_mask(self, success: bool):
        """Record segmentation mask generation"""
        status = "success" if success else "failure"
        segmentation_masks_generated.labels(status=status).inc()


# Global metrics collector instance
metrics_collector = MetricsCollector()


class MetricsTimer:
    """Context manager for timing operations"""

    def __init__(self, callback):
        self.callback = callback
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.callback(duration)
        return False
