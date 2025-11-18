"""Unit tests for orchestrator metrics collection"""

import pytest
import time
from src.monitoring.metrics import MetricsCollector, MetricsTimer


class TestMetricsCollector:
    """Tests for MetricsCollector"""

    @pytest.fixture
    def collector(self):
        """Create metrics collector for testing"""
        return MetricsCollector()

    def test_record_request(self, collector):
        """Test recording a request"""
        collector.record_request(
            detection_type="damage",
            priority="high",
            status="completed",
            duration_seconds=0.5
        )

        # Check that latency was stored
        key = "damage_completed"
        assert key in collector.latencies
        assert len(collector.latencies[key]) == 1
        assert collector.latencies[key][0] == 500.0  # 0.5s = 500ms

    def test_record_multiple_requests(self, collector):
        """Test recording multiple requests"""
        for i in range(10):
            collector.record_request(
                detection_type="damage",
                priority="normal",
                status="completed",
                duration_seconds=0.1 * (i + 1)
            )

        key = "damage_completed"
        assert len(collector.latencies[key]) == 10

    def test_max_latency_samples_limit(self, collector):
        """Test that latency samples are limited"""
        collector.max_latency_samples = 100

        # Add more than max samples
        for i in range(150):
            collector.record_request(
                detection_type="damage",
                priority="normal",
                status="completed",
                duration_seconds=0.1
            )

        key = "damage_completed"
        assert len(collector.latencies[key]) == 100

    def test_record_engine_request(self, collector):
        """Test recording engine request"""
        collector.record_engine_request(
            engine_type="damage",
            status="success",
            duration_seconds=0.25,
            confidence=0.85,
            model_version="v1.2.0",
            endpoint="http://engine:8001"
        )

        # Should not raise any errors
        # Prometheus metrics are incremented internally

    def test_record_circuit_breaker_state(self, collector):
        """Test recording circuit breaker state"""
        collector.record_circuit_breaker_state("damage", "open")
        collector.record_circuit_breaker_state("material", "closed")

        # Should not raise any errors
        # Prometheus gauges are set internally

    def test_record_circuit_breaker_failure(self, collector):
        """Test recording circuit breaker failure"""
        collector.record_circuit_breaker_failure("damage")

        # Should not raise any errors
        # Prometheus counter is incremented internally

    def test_record_health_check(self, collector):
        """Test recording health check"""
        collector.record_health_check(
            engine_type="damage",
            endpoint="http://engine:8001",
            is_healthy=True,
            duration_seconds=0.05
        )

        # Should not raise any errors

    def test_get_latency_percentiles_empty(self, collector):
        """Test getting percentiles with no data"""
        percentiles = collector.get_latency_percentiles("damage", "completed")

        assert percentiles["p50"] == 0.0
        assert percentiles["p90"] == 0.0
        assert percentiles["p95"] == 0.0
        assert percentiles["p99"] == 0.0

    def test_get_latency_percentiles_single_value(self, collector):
        """Test getting percentiles with single value"""
        collector.record_request(
            detection_type="damage",
            priority="normal",
            status="completed",
            duration_seconds=0.5
        )

        percentiles = collector.get_latency_percentiles("damage", "completed")

        # All percentiles should be same value
        assert percentiles["p50"] == 500.0
        assert percentiles["p90"] == 500.0
        assert percentiles["p95"] == 500.0
        assert percentiles["p99"] == 500.0

    def test_get_latency_percentiles_multiple_values(self, collector):
        """Test getting percentiles with multiple values"""
        # Add 100 samples with increasing latency
        for i in range(100):
            collector.record_request(
                detection_type="damage",
                priority="normal",
                status="completed",
                duration_seconds=(i + 1) / 1000.0  # 1ms to 100ms
            )

        percentiles = collector.get_latency_percentiles("damage", "completed")

        # Verify percentile calculations
        assert percentiles["p50"] > 0
        assert percentiles["p90"] > percentiles["p50"]
        assert percentiles["p95"] > percentiles["p90"]
        assert percentiles["p99"] > percentiles["p95"]

    def test_get_latency_percentiles_different_status(self, collector):
        """Test percentiles are tracked separately by status"""
        # Add completed requests
        for i in range(10):
            collector.record_request(
                detection_type="damage",
                priority="normal",
                status="completed",
                duration_seconds=0.1
            )

        # Add failed requests with different latencies
        for i in range(10):
            collector.record_request(
                detection_type="damage",
                priority="normal",
                status="failed",
                duration_seconds=0.5
            )

        completed_percentiles = collector.get_latency_percentiles("damage", "completed")
        failed_percentiles = collector.get_latency_percentiles("damage", "failed")

        # Failed requests should have higher latency
        assert failed_percentiles["p50"] > completed_percentiles["p50"]


class TestMetricsTimer:
    """Tests for MetricsTimer context manager"""

    def test_metrics_timer(self):
        """Test metrics timer context manager"""
        duration_captured = None

        def callback(duration):
            nonlocal duration_captured
            duration_captured = duration

        with MetricsTimer(callback):
            time.sleep(0.1)  # Sleep for 100ms

        # Duration should be approximately 0.1 seconds
        assert duration_captured is not None
        assert 0.09 < duration_captured < 0.15  # Allow some variance

    def test_metrics_timer_with_exception(self):
        """Test metrics timer still records time on exception"""
        duration_captured = None

        def callback(duration):
            nonlocal duration_captured
            duration_captured = duration

        try:
            with MetricsTimer(callback):
                time.sleep(0.05)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Duration should still be recorded
        assert duration_captured is not None
        assert duration_captured > 0

    def test_metrics_timer_zero_duration(self):
        """Test metrics timer with minimal duration"""
        duration_captured = None

        def callback(duration):
            nonlocal duration_captured
            duration_captured = duration

        with MetricsTimer(callback):
            pass  # No delay

        # Duration should be very small but captured
        assert duration_captured is not None
        assert duration_captured >= 0
