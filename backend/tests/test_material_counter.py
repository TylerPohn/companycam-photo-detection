"""Tests for density estimation material counter"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.material_detection import MaterialCounter, CounterConfig, MaterialDetector
from src.schemas.material_detection import MaterialType, BoundingBox


@pytest.fixture
def counter_config():
    """Create counter config for testing"""
    return CounterConfig(
        confidence_threshold=0.5,
        merge_distance_threshold=50,
        device="cpu",
    )


@pytest.fixture
def counter(counter_config):
    """Create material counter instance"""
    return MaterialCounter(counter_config)


@pytest.fixture
def sample_image():
    """Create sample test image"""
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


@pytest.fixture
def sample_detections():
    """Create sample detections for testing"""
    from src.ai_models.material_detection.detector import DetectionResult

    detections = [
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.85,
            bounding_box=BoundingBox(x=10, y=10, width=100, height=100, confidence=0.85),
        ),
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.82,
            bounding_box=BoundingBox(x=120, y=10, width=100, height=100, confidence=0.82),
        ),
        DetectionResult(
            material_type=MaterialType.PLYWOOD,
            confidence=0.78,
            bounding_box=BoundingBox(x=10, y=120, width=100, height=100, confidence=0.78),
        ),
    ]
    return detections


def test_counter_initialization(counter, counter_config):
    """Test counter initializes correctly"""
    assert counter.config == counter_config
    assert not counter.model_loaded
    assert counter.inference_count == 0


def test_counter_load_model(counter):
    """Test model loading"""
    counter.load_model()
    assert counter.model_loaded


def test_counter_count_materials(counter, sample_image, sample_detections):
    """Test material counting"""
    count_results = counter.count_materials(sample_image, sample_detections)

    # Should return dict
    assert isinstance(count_results, dict)

    # Should have loaded model
    assert counter.model_loaded

    # Should have counts for material types in detections
    assert MaterialType.SHINGLES in count_results
    assert MaterialType.PLYWOOD in count_results

    # Check count results
    shingles_result = count_results[MaterialType.SHINGLES]
    assert shingles_result.count > 0
    assert shingles_result.confidence > 0
    assert isinstance(shingles_result.refined_boxes, list)


def test_counter_grouping_by_type(counter, sample_detections):
    """Test that detections are grouped by material type"""
    grouped = counter._group_by_type(sample_detections)

    assert MaterialType.SHINGLES in grouped
    assert MaterialType.PLYWOOD in grouped

    # Shingles should have 2 detections
    assert len(grouped[MaterialType.SHINGLES]) == 2

    # Plywood should have 1 detection
    assert len(grouped[MaterialType.PLYWOOD]) == 1


def test_counter_merge_nearby_boxes(counter):
    """Test merging nearby bounding boxes"""
    from src.ai_models.material_detection.detector import DetectionResult

    # Create detections with overlapping boxes
    detections = [
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.90,
            bounding_box=BoundingBox(x=10, y=10, width=100, height=100, confidence=0.90),
        ),
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.85,
            bounding_box=BoundingBox(x=20, y=20, width=100, height=100, confidence=0.85),
        ),
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.80,
            bounding_box=BoundingBox(x=200, y=200, width=100, height=100, confidence=0.80),
        ),
    ]

    merged = counter._merge_nearby_boxes(detections)

    # Should merge the two overlapping boxes
    assert len(merged) < len(detections)
    assert len(merged) >= 1


def test_counter_iou_calculation(counter):
    """Test IoU calculation"""
    box1 = BoundingBox(x=0, y=0, width=100, height=100, confidence=0.9)
    box2 = BoundingBox(x=50, y=50, width=100, height=100, confidence=0.8)

    iou = counter._calculate_iou(box1, box2)

    # Should have some overlap
    assert 0.0 < iou < 1.0

    # Test no overlap
    box3 = BoundingBox(x=200, y=200, width=100, height=100, confidence=0.8)
    iou_no_overlap = counter._calculate_iou(box1, box3)
    assert iou_no_overlap == 0.0

    # Test perfect overlap
    box4 = BoundingBox(x=0, y=0, width=100, height=100, confidence=0.8)
    iou_perfect = counter._calculate_iou(box1, box4)
    assert iou_perfect == 1.0


def test_counter_empty_detections(counter, sample_image):
    """Test counting with no detections"""
    count_results = counter.count_materials(sample_image, [])

    # Should return empty dict
    assert count_results == {}


def test_counter_single_detection(counter, sample_image):
    """Test counting with single detection"""
    from src.ai_models.material_detection.detector import DetectionResult

    detections = [
        DetectionResult(
            material_type=MaterialType.PLYWOOD,
            confidence=0.88,
            bounding_box=BoundingBox(x=10, y=10, width=100, height=100, confidence=0.88),
        ),
    ]

    count_results = counter.count_materials(sample_image, detections)

    assert MaterialType.PLYWOOD in count_results
    plywood_result = count_results[MaterialType.PLYWOOD]
    assert plywood_result.count >= 1
    assert plywood_result.confidence > 0


def test_counter_stats(counter, sample_image, sample_detections):
    """Test getting counter stats"""
    # Before counting
    stats = counter.get_inference_stats()
    assert not stats["model_loaded"]
    assert stats["inference_count"] == 0

    # After counting
    counter.count_materials(sample_image, sample_detections)

    stats = counter.get_inference_stats()
    assert stats["model_loaded"]
    assert stats["inference_count"] == 1


def test_counter_confidence_averaging(counter, sample_image):
    """Test that confidence is averaged correctly"""
    from src.ai_models.material_detection.detector import DetectionResult

    # Create detections with different confidences
    detections = [
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.90,
            bounding_box=BoundingBox(x=10, y=10, width=100, height=100, confidence=0.90),
        ),
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.70,
            bounding_box=BoundingBox(x=150, y=150, width=100, height=100, confidence=0.70),
        ),
    ]

    count_results = counter.count_materials(sample_image, detections)
    shingles_result = count_results[MaterialType.SHINGLES]

    # Confidence should be average (around 0.80)
    assert 0.75 <= shingles_result.confidence <= 0.85


@pytest.mark.performance
def test_counter_latency(counter, sample_image, sample_detections):
    """Test that counting meets latency target"""
    import time

    # Warm up
    counter.load_model()

    # Measure inference time
    start_time = time.time()
    count_results = counter.count_materials(sample_image, sample_detections)
    inference_time_ms = (time.time() - start_time) * 1000

    # Should be fast (target < 120ms per story notes)
    assert inference_time_ms < 150  # Allow some margin
    print(f"Counting latency: {inference_time_ms:.2f}ms")


def test_counter_multiple_images(counter):
    """Test processing multiple images"""
    from src.ai_models.material_detection.detector import DetectionResult

    images = [
        Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        for _ in range(3)
    ]

    detections = [
        DetectionResult(
            material_type=MaterialType.SHINGLES,
            confidence=0.85,
            bounding_box=BoundingBox(x=10, y=10, width=100, height=100, confidence=0.85),
        ),
    ]

    for img in images:
        count_results = counter.count_materials(img, detections)
        assert isinstance(count_results, dict)

    # Should have run inference 3 times
    assert counter.inference_count == 3


def test_counter_refined_boxes(counter, sample_image, sample_detections):
    """Test that refined boxes are returned"""
    count_results = counter.count_materials(sample_image, sample_detections)

    for material_type, count_result in count_results.items():
        # Should have refined boxes
        assert isinstance(count_result.refined_boxes, list)

        # All boxes should be valid BoundingBox objects
        for bbox in count_result.refined_boxes:
            assert isinstance(bbox, BoundingBox)
            assert bbox.x >= 0
            assert bbox.y >= 0
            assert bbox.width > 0
            assert bbox.height > 0
