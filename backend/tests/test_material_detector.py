"""Tests for YOLOv8 material detector"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.material_detection import MaterialDetector, DetectorConfig
from src.schemas.material_detection import MaterialType


@pytest.fixture
def detector_config():
    """Create detector config for testing"""
    return DetectorConfig(
        confidence_threshold=0.65,
        max_detections=50,
        device="cpu",
    )


@pytest.fixture
def detector(detector_config):
    """Create material detector instance"""
    return MaterialDetector(detector_config)


@pytest.fixture
def sample_image():
    """Create sample test image"""
    # Create a simple RGB image (640x480)
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


def test_detector_initialization(detector, detector_config):
    """Test detector initializes correctly"""
    assert detector.config == detector_config
    assert not detector.model_loaded
    assert detector.inference_count == 0


def test_detector_load_model(detector):
    """Test model loading"""
    detector.load_model()
    assert detector.model_loaded


def test_detector_preprocess_image(detector, sample_image):
    """Test image preprocessing"""
    processed_img, original_size = detector.preprocess_image(sample_image)

    # Check original size preserved
    assert original_size == sample_image.size

    # Check preprocessed image shape
    assert processed_img.shape == (640, 640, 3)

    # Check normalization (values should be 0-1)
    assert processed_img.min() >= 0.0
    assert processed_img.max() <= 1.0


def test_detector_detect(detector, sample_image):
    """Test material detection"""
    detections = detector.detect(sample_image)

    # Should return list
    assert isinstance(detections, list)

    # Model should be loaded after first detection
    assert detector.model_loaded

    # Should have run inference
    assert detector.inference_count == 1

    # Check detection results
    for detection in detections:
        # Should detect valid material types
        assert isinstance(detection.material_type, MaterialType)

        # Confidence should be within threshold
        assert detection.confidence >= detector.config.confidence_threshold
        assert detection.confidence <= 1.0

        # Should have bounding box
        assert detection.bounding_box is not None
        assert detection.bounding_box.x >= 0
        assert detection.bounding_box.y >= 0
        assert detection.bounding_box.width > 0
        assert detection.bounding_box.height > 0


def test_detector_confidence_filtering(detector, sample_image):
    """Test that detections are filtered by confidence threshold"""
    # Set high threshold
    detector.config.confidence_threshold = 0.95

    detections = detector.detect(sample_image)

    # All detections should meet threshold
    for detection in detections:
        assert detection.confidence >= 0.95


def test_detector_max_detections(detector, sample_image):
    """Test max detections limit"""
    detector.config.max_detections = 5

    detections = detector.detect(sample_image)

    # Should not exceed max detections
    assert len(detections) <= 5


def test_detector_multiple_images(detector):
    """Test processing multiple images"""
    # Create multiple test images
    images = [
        Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        for _ in range(3)
    ]

    for img in images:
        detections = detector.detect(img)
        assert isinstance(detections, list)

    # Should have run inference 3 times
    assert detector.inference_count == 3


def test_detector_stats(detector, sample_image):
    """Test getting detector stats"""
    # Before detection
    stats = detector.get_inference_stats()
    assert not stats["model_loaded"]
    assert stats["inference_count"] == 0

    # After detection
    detector.detect(sample_image)

    stats = detector.get_inference_stats()
    assert stats["model_loaded"]
    assert stats["inference_count"] == 1
    assert "config" in stats


def test_detector_material_types(detector, sample_image):
    """Test that various material types can be detected"""
    # Run multiple detections to get variety
    all_material_types = set()

    for _ in range(5):
        detections = detector.detect(sample_image)
        for detection in detections:
            all_material_types.add(detection.material_type)

    # Should detect at least some material types
    assert len(all_material_types) > 0

    # All should be valid MaterialType enum values
    for mat_type in all_material_types:
        assert mat_type in MaterialType


def test_detector_bounding_box_validity(detector, sample_image):
    """Test that bounding boxes are valid and within image bounds"""
    detections = detector.detect(sample_image)

    img_width, img_height = sample_image.size

    for detection in detections:
        bbox = detection.bounding_box

        # Bounding box should be within image
        assert bbox.x >= 0
        assert bbox.y >= 0
        assert bbox.x + bbox.width <= img_width
        assert bbox.y + bbox.height <= img_height

        # Confidence should match detection confidence
        assert abs(bbox.confidence - detection.confidence) < 0.01


@pytest.mark.performance
def test_detector_latency(detector, sample_image):
    """Test that detection meets latency target"""
    import time

    # Warm up
    detector.load_model()

    # Measure inference time
    start_time = time.time()
    detections = detector.detect(sample_image)
    inference_time_ms = (time.time() - start_time) * 1000

    # Should be fast (target < 160ms per story notes)
    assert inference_time_ms < 200  # Allow some margin for mock implementation
    print(f"Detection latency: {inference_time_ms:.2f}ms")


def test_detector_edge_cases():
    """Test edge cases for detector"""
    detector = MaterialDetector()

    # Very small image
    small_img = Image.fromarray(np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8))
    detections = detector.detect(small_img)
    assert isinstance(detections, list)

    # Very large image
    large_img = Image.fromarray(np.random.randint(0, 255, (2000, 3000, 3), dtype=np.uint8))
    detections = detector.detect(large_img)
    assert isinstance(detections, list)

    # Grayscale image (should convert to RGB)
    gray_img = Image.fromarray(np.random.randint(0, 255, (480, 640), dtype=np.uint8))
    detections = detector.detect(gray_img)
    assert isinstance(detections, list)
