"""Tests for Scale Reference Detection"""

import pytest
import numpy as np
from src.ai_models.volume_estimation.scale_detector import ScaleDetector, MockYOLOModel
from src.ai_models.volume_estimation.config import ScaleDetectionConfig


@pytest.fixture
def scale_config():
    """Create scale detection config"""
    return ScaleDetectionConfig(device="cpu")


@pytest.fixture
def scale_detector(scale_config):
    """Create and load scale detector"""
    detector = ScaleDetector(scale_config)
    detector.load_model()
    return detector


@pytest.fixture
def sample_image():
    """Create a sample RGB image"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


def test_scale_detector_initialization(scale_config):
    """Test scale detector initialization"""
    detector = ScaleDetector(scale_config)
    assert detector.config == scale_config
    assert detector.model is None
    assert detector._inference_count == 0


def test_load_model(scale_detector):
    """Test model loading"""
    assert scale_detector.model is not None
    assert isinstance(scale_detector.model, MockYOLOModel)
    assert scale_detector.reference_data is not None


def test_detect_scale_reference(scale_detector, sample_image):
    """Test scale reference detection"""
    scale_reference, metadata = scale_detector.detect_scale_reference(sample_image)

    # Check metadata
    assert "inference_time_ms" in metadata
    assert "num_detections" in metadata
    assert "has_scale_reference" in metadata
    assert metadata["inference_time_ms"] > 0

    # scale_reference can be None if nothing detected
    if scale_reference:
        assert "type" in scale_reference
        assert "confidence" in scale_reference
        assert "pixels_per_cm" in scale_reference


def test_select_best_reference(scale_detector):
    """Test selecting best reference from detections"""
    detections = [
        {"class": "car", "confidence": 0.9, "bbox": (100, 100, 200, 300)},
        {"class": "person", "confidence": 0.85, "bbox": (300, 200, 350, 400)},
    ]

    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    best_ref = scale_detector._select_best_reference(detections, image, None)

    # Person has higher priority than car
    assert best_ref is not None
    assert best_ref["type"] == "person"


def test_extract_scale_info(scale_detector):
    """Test extracting scale information from detection"""
    detection = {
        "class": "person",
        "confidence": 0.85,
        "bbox": (100, 100, 150, 300)
    }

    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    scale_info = scale_detector._extract_scale_info(detection, image, None)

    assert scale_info["type"] == "person"
    assert scale_info["confidence"] > 0
    assert scale_info["estimated_height_cm"] is not None
    assert scale_info["pixels_per_cm"] > 0
    assert scale_info["pixel_dimension"] == 200  # y2 - y1


def test_enhance_with_depth(scale_detector):
    """Test enhancing scale reference with depth"""
    scale_reference = {
        "type": "person",
        "confidence": 0.85,
        "pixels_per_cm": 2.0
    }

    depth_map = np.random.rand(480, 640).astype(np.float32)
    bbox = (100, 100, 150, 300)

    enhanced = scale_detector._enhance_with_depth(scale_reference, depth_map, bbox)

    assert "reference_depth" in enhanced
    assert enhanced["reference_depth"] >= 0.0


def test_get_stats(scale_detector, sample_image):
    """Test statistics retrieval"""
    # Run some detections
    scale_detector.detect_scale_reference(sample_image)
    scale_detector.detect_scale_reference(sample_image)

    stats = scale_detector.get_stats()

    assert stats["inference_count"] == 2
    assert stats["average_inference_time_ms"] > 0
    assert stats["model_type"] == scale_detector.config.model_type


def test_mock_yolo_model():
    """Test mock YOLO model"""
    model = MockYOLOModel("yolov8n", "cpu")

    # Create test image
    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Run multiple predictions (should detect person ~60% of time)
    detections_list = [model.predict(image) for _ in range(20)]

    # At least some should have detections
    has_detections = sum(1 for d in detections_list if len(d) > 0)
    assert has_detections > 0

    # Check detection format
    for detections in detections_list:
        if detections:
            detection = detections[0]
            assert "class" in detection
            assert "confidence" in detection
            assert "bbox" in detection
            assert len(detection["bbox"]) == 4
