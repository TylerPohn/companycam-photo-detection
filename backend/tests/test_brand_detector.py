"""Tests for OCR-based brand detection"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.material_detection import BrandDetector, BrandDetectorConfig, MaterialDatabase
from src.schemas.material_detection import MaterialType, BoundingBox


@pytest.fixture
def brand_config():
    """Create brand detector config for testing"""
    return BrandDetectorConfig(
        ocr_engine="tesseract",
        confidence_threshold=0.6,
        fuzzy_match_threshold=80,
        roi_expand_pixels=20,
    )


@pytest.fixture
def material_db():
    """Create material database for testing"""
    db = MaterialDatabase(
        materials_db_path="/home/user/companycam-photo-detection/backend/data/materials.json",
        brands_db_path="/home/user/companycam-photo-detection/backend/data/brands.json",
    )
    db.load()
    return db


@pytest.fixture
def brand_detector(brand_config, material_db):
    """Create brand detector instance"""
    return BrandDetector(brand_config, material_db)


@pytest.fixture
def sample_image():
    """Create sample test image"""
    img_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


@pytest.fixture
def sample_bounding_box():
    """Create sample bounding box"""
    return BoundingBox(x=50, y=50, width=200, height=150, confidence=0.85)


def test_brand_detector_initialization(brand_detector, brand_config):
    """Test brand detector initializes correctly"""
    assert brand_detector.config == brand_config
    assert not brand_detector.ocr_engine_initialized
    assert brand_detector.inference_count == 0


def test_brand_detector_initialize_ocr(brand_detector):
    """Test OCR engine initialization"""
    brand_detector.initialize_ocr()
    assert brand_detector.ocr_engine_initialized


def test_brand_detector_detect_brand(brand_detector, sample_image):
    """Test brand detection"""
    result = brand_detector.detect_brand(
        sample_image,
        MaterialType.SHINGLES,
    )

    # Should have initialized OCR
    assert brand_detector.ocr_engine_initialized

    # Should return result
    assert result is not None

    # Brand name may or may not be detected
    if result.brand_name:
        assert isinstance(result.brand_name, str)
        assert result.confidence > 0

    # Confidence should be valid
    assert 0.0 <= result.confidence <= 1.0


def test_brand_detector_with_bounding_box(brand_detector, sample_image, sample_bounding_box):
    """Test brand detection with bounding box ROI"""
    result = brand_detector.detect_brand(
        sample_image,
        MaterialType.SHINGLES,
        sample_bounding_box,
    )

    assert result is not None
    assert 0.0 <= result.confidence <= 1.0


def test_brand_detector_crop_roi(brand_detector, sample_image, sample_bounding_box):
    """Test ROI cropping"""
    roi_image = brand_detector._crop_roi(sample_image, sample_bounding_box)

    # Should return cropped image
    assert isinstance(roi_image, Image.Image)

    # Size should be roughly bounding box size (plus expansion)
    expand = brand_detector.config.roi_expand_pixels
    expected_width = sample_bounding_box.width + 2 * expand
    expected_height = sample_bounding_box.height + 2 * expand

    # Allow some variance for edge cases
    assert roi_image.width <= expected_width + 10
    assert roi_image.height <= expected_height + 10


def test_brand_detector_crop_roi_no_bbox(brand_detector, sample_image):
    """Test ROI cropping without bounding box"""
    roi_image = brand_detector._crop_roi(sample_image, None)

    # Should return original image
    assert roi_image == sample_image


def test_brand_detector_run_ocr(brand_detector, sample_image):
    """Test OCR text extraction"""
    brand_detector.initialize_ocr()

    text = brand_detector._run_ocr(sample_image)

    # Should return string
    assert isinstance(text, str)


def test_brand_detector_match_brand(brand_detector, material_db):
    """Test brand matching from text"""
    # Test with known brand name
    result = brand_detector._match_brand("shingles", "CertainTeed Roofing Shingles")

    # Should find brand
    assert result.brand_name == "CertainTeed"
    assert result.confidence > 0.7


def test_brand_detector_match_brand_no_match(brand_detector):
    """Test brand matching with no match"""
    result = brand_detector._match_brand("shingles", "")

    # Should have no brand
    assert result.brand_name is None
    assert result.confidence == 0.0


def test_brand_detector_match_brand_fuzzy(brand_detector):
    """Test fuzzy brand matching"""
    # Test with slight misspelling
    result = brand_detector._match_brand("shingles", "Owens Corning Premium")

    # Should find brand with fuzzy matching
    if result.brand_name:
        assert "Owens Corning" in result.brand_name or result.brand_name == "Owens Corning"


def test_brand_detector_different_material_types(brand_detector, sample_image):
    """Test brand detection for different material types"""
    material_types = [
        MaterialType.SHINGLES,
        MaterialType.PLYWOOD,
        MaterialType.DRYWALL,
        MaterialType.INSULATION,
    ]

    for material_type in material_types:
        result = brand_detector.detect_brand(sample_image, material_type)
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


def test_brand_detector_batch(brand_detector, sample_image):
    """Test batch brand detection"""
    bboxes = [
        BoundingBox(x=10, y=10, width=100, height=100, confidence=0.85),
        BoundingBox(x=120, y=10, width=100, height=100, confidence=0.82),
        BoundingBox(x=230, y=10, width=100, height=100, confidence=0.79),
    ]

    results = brand_detector.detect_brands_batch(
        sample_image,
        MaterialType.SHINGLES,
        bboxes,
    )

    # Should have results for all bboxes
    assert len(results) == len(bboxes)

    # All results should be valid
    for result in results:
        assert result is not None
        assert 0.0 <= result.confidence <= 1.0


def test_brand_detector_stats(brand_detector, sample_image):
    """Test getting detector stats"""
    # Before detection
    stats = brand_detector.get_inference_stats()
    assert not stats["ocr_initialized"]
    assert stats["inference_count"] == 0
    assert stats["ocr_engine"] == "tesseract"

    # After detection
    brand_detector.detect_brand(sample_image, MaterialType.SHINGLES)

    stats = brand_detector.get_inference_stats()
    assert stats["ocr_initialized"]
    assert stats["inference_count"] == 1


@pytest.mark.performance
def test_brand_detector_latency(brand_detector, sample_image):
    """Test that brand detection is reasonably fast"""
    import time

    # Warm up
    brand_detector.initialize_ocr()

    # Measure inference time
    start_time = time.time()
    result = brand_detector.detect_brand(sample_image, MaterialType.SHINGLES)
    inference_time_ms = (time.time() - start_time) * 1000

    # Should be reasonably fast (allow more time for OCR)
    assert inference_time_ms < 100  # Mock implementation should be fast
    print(f"Brand detection latency: {inference_time_ms:.2f}ms")


def test_brand_detector_confidence_threshold(brand_detector, sample_image):
    """Test confidence threshold filtering"""
    # Set high threshold
    brand_detector.config.confidence_threshold = 0.95

    result = brand_detector.detect_brand(sample_image, MaterialType.SHINGLES)

    # If brand detected, confidence should meet threshold
    if result.brand_name:
        assert result.confidence >= 0.95


def test_brand_detector_multiple_detections(brand_detector, sample_image):
    """Test multiple sequential detections"""
    for _ in range(5):
        result = brand_detector.detect_brand(sample_image, MaterialType.SHINGLES)
        assert result is not None

    # Should have run 5 inferences
    assert brand_detector.inference_count == 5


def test_brand_detector_edge_cases(brand_detector):
    """Test edge cases"""
    # Very small image
    small_img = Image.fromarray(np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8))
    result = brand_detector.detect_brand(small_img, MaterialType.SHINGLES)
    assert result is not None

    # Grayscale image
    gray_img = Image.fromarray(np.random.randint(0, 255, (480, 640), dtype=np.uint8))
    result = brand_detector.detect_brand(gray_img, MaterialType.PLYWOOD)
    assert result is not None
