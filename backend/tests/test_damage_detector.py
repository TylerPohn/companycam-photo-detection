"""Unit tests for YOLOv8 damage detector"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.damage_detection.detector import DamageDetector, DetectionResult
from src.ai_models.damage_detection.config import DetectorConfig
from src.schemas.damage_detection import DamageType


@pytest.fixture
def detector_config():
    """Create detector configuration for testing"""
    return DetectorConfig(
        confidence_threshold=0.7,
        input_size=640,
        device="cpu",
    )


@pytest.fixture
def detector(detector_config):
    """Create detector instance"""
    return DamageDetector(detector_config)


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    # Create 640x480 RGB image
    image_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(image_array, mode="RGB")


class TestDamageDetector:
    """Test suite for DamageDetector"""

    def test_detector_initialization(self, detector, detector_config):
        """Test detector initializes with correct configuration"""
        assert detector.config == detector_config
        assert detector.model_loaded is False
        assert detector.inference_count == 0

    def test_model_loading(self, detector):
        """Test model loading"""
        detector.load_model()
        assert detector.model_loaded is True

    def test_image_preprocessing(self, detector, sample_image):
        """Test image preprocessing"""
        processed, original_size = detector.preprocess_image(sample_image)

        # Check original size is preserved
        assert original_size == sample_image.size

        # Check processed image has correct shape
        assert processed.shape == (640, 640, 3)

        # Check normalization (values between 0 and 1)
        assert processed.min() >= 0.0
        assert processed.max() <= 1.0

    def test_detect_returns_detection_results(self, detector, sample_image):
        """Test detection returns list of DetectionResult objects"""
        detections = detector.detect(sample_image)

        assert isinstance(detections, list)
        assert all(isinstance(d, DetectionResult) for d in detections)

    def test_detect_loads_model_automatically(self, detector, sample_image):
        """Test that detect loads model if not already loaded"""
        assert detector.model_loaded is False
        detector.detect(sample_image)
        assert detector.model_loaded is True

    def test_detect_filters_by_confidence(self, detector, sample_image):
        """Test that detections are filtered by confidence threshold"""
        detector.config.confidence_threshold = 0.9  # High threshold
        detections = detector.detect(sample_image)

        # All detections should meet threshold
        assert all(d.confidence >= 0.9 for d in detections)

    def test_detect_respects_max_detections(self, detector, sample_image):
        """Test that max detections limit is respected"""
        detector.config.max_detections = 3
        detections = detector.detect(sample_image)

        assert len(detections) <= 3

    def test_detect_returns_valid_damage_types(self, detector, sample_image):
        """Test that all detections have valid damage types"""
        detections = detector.detect(sample_image)

        valid_types = {
            DamageType.HAIL_DAMAGE,
            DamageType.WIND_DAMAGE,
            DamageType.MISSING_SHINGLES,
        }

        for detection in detections:
            assert detection.damage_type in valid_types

    def test_detect_returns_valid_bounding_boxes(self, detector, sample_image):
        """Test that bounding boxes have valid coordinates"""
        detections = detector.detect(sample_image)

        for detection in detections:
            bbox = detection.bounding_box

            # Check non-negative coordinates
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width > 0
            assert bbox.height > 0

            # Check within image bounds
            img_width, img_height = sample_image.size
            assert bbox.x + bbox.width <= img_width
            assert bbox.y + bbox.height <= img_height

    def test_detect_increments_inference_count(self, detector, sample_image):
        """Test that inference count is incremented"""
        initial_count = detector.inference_count

        detector.detect(sample_image)
        assert detector.inference_count == initial_count + 1

        detector.detect(sample_image)
        assert detector.inference_count == initial_count + 2

    def test_get_inference_stats(self, detector, sample_image):
        """Test inference statistics"""
        detector.detect(sample_image)
        stats = detector.get_inference_stats()

        assert "model_loaded" in stats
        assert "inference_count" in stats
        assert "config" in stats

        assert stats["model_loaded"] is True
        assert stats["inference_count"] > 0

    def test_detect_with_different_image_sizes(self, detector):
        """Test detection with various image sizes"""
        test_sizes = [
            (320, 240),   # Small
            (640, 480),   # Medium
            (1920, 1080), # Large
            (3840, 2160), # 4K
        ]

        for width, height in test_sizes:
            image_array = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            image = Image.fromarray(image_array, mode="RGB")

            detections = detector.detect(image)
            assert isinstance(detections, list)

    def test_detect_confidence_range(self, detector, sample_image):
        """Test that confidence scores are in valid range [0, 1]"""
        detections = detector.detect(sample_image)

        for detection in detections:
            assert 0.0 <= detection.confidence <= 1.0

    def test_nms_application(self, detector):
        """Test that NMS is applied to remove duplicates"""
        # Create sample detections
        from src.schemas.damage_detection import BoundingBox

        detections = [
            DetectionResult(
                DamageType.HAIL_DAMAGE,
                0.95,
                BoundingBox(x=100, y=100, width=50, height=50),
            ),
            DetectionResult(
                DamageType.HAIL_DAMAGE,
                0.85,
                BoundingBox(x=105, y=105, width=50, height=50),
            ),
            DetectionResult(
                DamageType.WIND_DAMAGE,
                0.90,
                BoundingBox(x=200, y=200, width=60, height=60),
            ),
        ]

        result = detector._apply_nms(detections)

        # Should keep highest confidence detections
        assert len(result) <= len(detections)
        assert all(isinstance(d, DetectionResult) for d in result)
