"""Integration tests for damage detection pipeline"""

import pytest
from PIL import Image
import numpy as np
from unittest.mock import Mock, AsyncMock, patch

from src.ai_models.damage_detection.pipeline import DamageDetectionPipeline
from src.ai_models.damage_detection.config import DamageDetectionConfig
from src.schemas.damage_detection import DamageDetectionResponse


@pytest.fixture
def pipeline_config():
    """Create pipeline configuration for testing"""
    return DamageDetectionConfig(
        model_version="damage-v1.2.0-test",
        enable_segmentation=True,
        enable_severity=True,
    )


@pytest.fixture
def pipeline(pipeline_config):
    """Create pipeline instance"""
    return DamageDetectionPipeline(pipeline_config)


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    image_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(image_array, mode="RGB")


@pytest.fixture
def mock_s3_service():
    """Create mock S3 service"""
    service = Mock()
    service.upload_bytes = Mock(
        return_value="https://s3.amazonaws.com/bucket/masks/test_damage0.png"
    )
    return service


class TestDamageDetectionPipeline:
    """Test suite for DamageDetectionPipeline"""

    def test_pipeline_initialization(self, pipeline, pipeline_config):
        """Test pipeline initializes with correct configuration"""
        assert pipeline.config == pipeline_config
        assert pipeline.pipeline_loaded is False

    def test_load_models(self, pipeline):
        """Test loading all models"""
        pipeline.load_models()

        assert pipeline.pipeline_loaded is True
        assert pipeline.detector.model_loaded is True
        assert pipeline.segmenter.model_loaded is True
        assert pipeline.severity_classifier.model_loaded is True

    def test_process_image_returns_valid_response(self, pipeline, sample_image):
        """Test processing image returns valid DamageDetectionResponse"""
        response = pipeline.process_image(sample_image)

        assert isinstance(response, DamageDetectionResponse)
        assert isinstance(response.detections, list)
        assert isinstance(response.tags, list)
        assert response.model_version == pipeline.config.model_version
        assert response.processing_time_ms > 0
        assert 0.0 <= response.confidence <= 1.0

    def test_process_image_loads_models_automatically(self, pipeline, sample_image):
        """Test that process_image loads models if not already loaded"""
        assert pipeline.pipeline_loaded is False
        pipeline.process_image(sample_image)
        assert pipeline.pipeline_loaded is True

    def test_process_image_with_s3_service(
        self, pipeline, sample_image, mock_s3_service
    ):
        """Test processing with S3 service uploads masks"""
        response = pipeline.process_image(
            sample_image, s3_service=mock_s3_service, photo_id="test_photo"
        )

        # If detections were found, S3 should have been called
        if response.detections:
            assert mock_s3_service.upload_bytes.called

    def test_process_image_without_segmentation(self, pipeline, sample_image):
        """Test processing without segmentation"""
        pipeline.config.enable_segmentation = False
        response = pipeline.process_image(sample_image)

        # Segmentation masks should be None
        for detection in response.detections:
            assert detection.segmentation_mask is None

    def test_process_image_without_severity(self, pipeline, sample_image):
        """Test processing without severity classification"""
        pipeline.config.enable_severity = False
        response = pipeline.process_image(sample_image)

        # Should still return valid response
        assert isinstance(response, DamageDetectionResponse)

    def test_summary_generation(self, pipeline, sample_image):
        """Test summary statistics generation"""
        response = pipeline.process_image(sample_image)

        summary = response.summary

        # Check summary fields
        assert hasattr(summary, "total_damage_area_percentage")
        assert hasattr(summary, "damage_type_distribution")

        assert 0.0 <= summary.total_damage_area_percentage <= 100.0
        assert isinstance(summary.damage_type_distribution, dict)

    def test_tag_generation(self, pipeline, sample_image):
        """Test tag generation based on detections"""
        response = pipeline.process_image(sample_image)

        tags = response.tags

        assert isinstance(tags, list)

        # If no detections, should have no_damage_detected tag
        if not response.detections:
            assert "no_damage_detected" in tags
        else:
            # If detections exist, should have roof_damage tag
            assert "roof_damage" in tags

    def test_confidence_calculation(self, pipeline, sample_image):
        """Test overall confidence calculation"""
        response = pipeline.process_image(sample_image)

        # If detections exist, confidence should be average
        if response.detections:
            expected_confidence = sum(
                d.confidence for d in response.detections
            ) / len(response.detections)

            assert abs(response.confidence - expected_confidence) < 0.01
        else:
            assert response.confidence == 0.0

    def test_processing_time_tracking(self, pipeline, sample_image):
        """Test that processing time is tracked"""
        response = pipeline.process_image(sample_image)

        # Processing time should be positive
        assert response.processing_time_ms > 0

        # Should be reasonable (less than 10 seconds for mock models)
        assert response.processing_time_ms < 10000

    def test_batch_processing(self, pipeline):
        """Test batch processing multiple images"""
        images = [
            Image.fromarray(
                np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8), mode="RGB"
            )
            for _ in range(3)
        ]

        photo_ids = ["photo1", "photo2", "photo3"]

        results = pipeline.process_batch(images, photo_ids=photo_ids)

        # Check all images processed
        assert len(results) == len(images)

        # Check photo_ids match
        for photo_id in photo_ids:
            assert photo_id in results

    def test_batch_processing_error_handling(self, pipeline):
        """Test batch processing handles errors gracefully"""
        # Mix of valid and invalid images
        images = [
            Image.fromarray(
                np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8), mode="RGB"
            ),
            None,  # This will cause an error
            Image.fromarray(
                np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8), mode="RGB"
            ),
        ]

        photo_ids = ["photo1", "photo2", "photo3"]

        # Should not raise exception
        results = pipeline.process_batch(images, photo_ids=photo_ids)

        # Should have processed valid images
        assert "photo1" in results

    def test_get_stats(self, pipeline, sample_image):
        """Test pipeline statistics"""
        # Process an image first
        pipeline.process_image(sample_image)

        stats = pipeline.get_stats()

        assert "pipeline_loaded" in stats
        assert "model_version" in stats
        assert "detector_stats" in stats
        assert "segmenter_stats" in stats
        assert "severity_classifier_stats" in stats

        assert stats["pipeline_loaded"] is True
        assert stats["model_version"] == pipeline.config.model_version

    def test_detection_area_percentage_calculation(self, pipeline, sample_image):
        """Test area percentage is calculated correctly"""
        response = pipeline.process_image(sample_image)

        for detection in response.detections:
            # Area percentage should be between 0 and 100
            assert 0.0 <= detection.area_percentage <= 100.0

    def test_tags_include_severity_markers(self, pipeline, sample_image):
        """Test tags include severity-based markers"""
        response = pipeline.process_image(sample_image)

        # If severe damage detected, should have appropriate tags
        has_severe = any(d.severity.value == "severe" for d in response.detections)

        if has_severe:
            assert "severe_damage" in response.tags or len(response.detections) == 0

    def test_tags_include_insurance_claim_marker(self, pipeline, sample_image):
        """Test tags include insurance claim marker for moderate/severe damage"""
        response = pipeline.process_image(sample_image)

        # If moderate or severe damage, should have insurance_claim tag
        has_claim_worthy = any(
            d.severity.value in ["moderate", "severe"] for d in response.detections
        )

        if has_claim_worthy:
            assert "insurance_claim" in response.tags or len(response.detections) == 0

    def test_multiple_damage_types_tag(self, pipeline, sample_image):
        """Test tag for multiple damages"""
        response = pipeline.process_image(sample_image)

        # If 5+ detections, should have multiple_damages tag
        if len(response.detections) >= 5:
            assert "multiple_damages" in response.tags

    def test_damage_type_distribution_accuracy(self, pipeline, sample_image):
        """Test damage type distribution is accurate"""
        response = pipeline.process_image(sample_image)

        # Count damage types manually
        from collections import Counter

        manual_count = Counter(d.type.value for d in response.detections)

        # Compare with summary distribution
        for damage_type, count in response.summary.damage_type_distribution.items():
            assert manual_count.get(damage_type, 0) == count

    def test_total_damage_area_calculation(self, pipeline, sample_image):
        """Test total damage area percentage calculation"""
        response = pipeline.process_image(sample_image)

        # Calculate manually
        manual_total = sum(d.area_percentage for d in response.detections)

        # Should match summary (clamped to 100)
        expected_total = min(100.0, manual_total)

        assert (
            abs(response.summary.total_damage_area_percentage - expected_total) < 0.01
        )

    def test_model_version_in_response(self, pipeline, sample_image):
        """Test model version is included in response"""
        response = pipeline.process_image(sample_image)

        assert response.model_version == pipeline.config.model_version
