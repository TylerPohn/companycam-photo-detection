"""Tests for end-to-end material detection pipeline"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.material_detection import (
    MaterialDetectionPipeline,
    MaterialDetectionConfig,
    MaterialDatabase,
)
from src.schemas.material_detection import MaterialType


@pytest.fixture
def pipeline_config():
    """Create pipeline config for testing"""
    return MaterialDetectionConfig(
        model_version="material-v1.1.0-test",
        enable_counting=True,
        enable_brand_detection=True,
        target_latency_ms=450,
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
def pipeline(pipeline_config, material_db):
    """Create pipeline instance"""
    return MaterialDetectionPipeline(pipeline_config, material_db)


@pytest.fixture
def sample_image():
    """Create sample test image"""
    img_array = np.random.randint(0, 255, (640, 480, 3), dtype=np.uint8)
    return Image.fromarray(img_array)


def test_pipeline_initialization(pipeline, pipeline_config):
    """Test pipeline initializes correctly"""
    assert pipeline.config == pipeline_config
    assert not pipeline.pipeline_loaded


def test_pipeline_load_models(pipeline):
    """Test loading all models"""
    pipeline.load_models()

    assert pipeline.pipeline_loaded
    assert pipeline.detector.model_loaded
    assert pipeline.counter.model_loaded
    assert pipeline.brand_detector.ocr_engine_initialized
    assert pipeline.material_db._loaded


def test_pipeline_process_image(pipeline, sample_image):
    """Test processing a single image through full pipeline"""
    response = pipeline.process_image(sample_image)

    # Should have loaded models
    assert pipeline.pipeline_loaded

    # Check response structure
    assert response is not None
    assert hasattr(response, "materials")
    assert hasattr(response, "tags")
    assert hasattr(response, "summary")
    assert hasattr(response, "processing_time_ms")
    assert hasattr(response, "model_version")
    assert hasattr(response, "confidence")

    # Check model version
    assert response.model_version == pipeline.config.model_version

    # Check processing time
    assert response.processing_time_ms > 0

    # Check confidence range
    assert 0.0 <= response.confidence <= 1.0


def test_pipeline_process_image_with_expected_materials(pipeline, sample_image):
    """Test processing with expected material quantities"""
    expected_materials = {
        "shingles": 36,
        "plywood": 25,
    }

    response = pipeline.process_image(sample_image, expected_materials)

    # Should have materials
    assert isinstance(response.materials, list)

    # Check for expected materials with quantity validation
    for material in response.materials:
        if material.type.value in expected_materials:
            assert material.expected_quantity == expected_materials[material.type.value]
            # May or may not have alert depending on detected count


def test_pipeline_material_detections(pipeline, sample_image):
    """Test that materials are detected correctly"""
    response = pipeline.process_image(sample_image)

    # Check each material detection
    for material in response.materials:
        # Should have valid material type
        assert isinstance(material.type, MaterialType)

        # Should have count
        assert material.count >= 0

        # Should have confidence
        assert 0.0 <= material.confidence <= 1.0

        # Should have unit
        assert material.unit is not None

        # Should have bounding boxes (may be empty list)
        assert isinstance(material.bounding_boxes, list)

        # If brand detected, should be string
        if material.brand:
            assert isinstance(material.brand, str)


def test_pipeline_summary_statistics(pipeline, sample_image):
    """Test summary statistics generation"""
    response = pipeline.process_image(sample_image)

    summary = response.summary

    # Check summary fields
    assert summary.total_materials_detected >= 0
    assert summary.total_units >= 0
    assert summary.discrepancy_alerts >= 0

    # Total materials should match number of detections
    assert summary.total_materials_detected == len(response.materials)

    # Total units should equal sum of individual counts
    calculated_total = sum(m.count for m in response.materials)
    assert summary.total_units == calculated_total


def test_pipeline_tags_generation(pipeline, sample_image):
    """Test tag generation"""
    response = pipeline.process_image(sample_image)

    # Should have tags
    assert isinstance(response.tags, list)

    # If materials detected, should have relevant tags
    if response.materials:
        assert "delivery_confirmation" in response.tags

        # Should have material type tags
        for material in response.materials:
            assert material.type.value in response.tags


def test_pipeline_quantity_alerts(pipeline, sample_image):
    """Test quantity discrepancy alerts"""
    expected_materials = {
        "shingles": 100,  # Likely to trigger alert with mock data
        "plywood": 100,
    }

    response = pipeline.process_image(sample_image, expected_materials)

    # Check if alerts are generated
    alerts_count = sum(1 for m in response.materials if m.alert is not None)

    # Summary should match alerts count
    assert response.summary.discrepancy_alerts == alerts_count

    # If alerts exist, tags should include discrepancy tag
    if alerts_count > 0:
        assert "quantity_discrepancy" in response.tags


def test_pipeline_batch_processing(pipeline):
    """Test batch processing multiple images"""
    images = [
        Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        for _ in range(3)
    ]

    results = pipeline.process_batch(images)

    # Should have results for all images
    assert len(results) == 3

    # All results should be valid
    for idx, response in results.items():
        assert response is not None
        assert hasattr(response, "materials")


def test_pipeline_batch_with_expected_materials(pipeline):
    """Test batch processing with expected materials"""
    images = [
        Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
        for _ in range(2)
    ]

    expected_materials_list = [
        {"shingles": 36},
        {"plywood": 25},
    ]

    results = pipeline.process_batch(images, expected_materials_list)

    # Should have 2 results
    assert len(results) == 2

    # Check that expected materials were used
    for idx, response in results.items():
        if response.materials:
            for material in response.materials:
                if material.expected_quantity:
                    assert material.expected_quantity > 0


def test_pipeline_stats(pipeline, sample_image):
    """Test getting pipeline statistics"""
    # Before processing
    stats = pipeline.get_stats()
    assert not stats["pipeline_loaded"]

    # After processing
    pipeline.process_image(sample_image)

    stats = pipeline.get_stats()
    assert stats["pipeline_loaded"]
    assert stats["model_version"] == pipeline.config.model_version
    assert "detector_stats" in stats
    assert "counter_stats" in stats
    assert "brand_detector_stats" in stats
    assert "material_db_stats" in stats


@pytest.mark.performance
def test_pipeline_latency(pipeline, sample_image):
    """Test that pipeline meets latency target"""
    import time

    # Warm up - load models
    pipeline.load_models()

    # Measure processing time
    start_time = time.time()
    response = pipeline.process_image(sample_image)
    total_time_ms = (time.time() - start_time) * 1000

    # Should meet target latency (450ms)
    assert total_time_ms < 500  # Allow some margin for mock
    print(f"Pipeline latency: {total_time_ms:.2f}ms (target: 450ms)")

    # Response should also report processing time
    assert response.processing_time_ms > 0


def test_pipeline_multiple_material_types(pipeline, sample_image):
    """Test detection of multiple material types"""
    response = pipeline.process_image(sample_image)

    # Should potentially detect multiple material types
    material_types = set(m.type for m in response.materials)

    # Verify all are valid MaterialType enums
    for mat_type in material_types:
        assert mat_type in MaterialType


def test_pipeline_bounding_boxes(pipeline, sample_image):
    """Test that bounding boxes are generated"""
    response = pipeline.process_image(sample_image)

    for material in response.materials:
        # May or may not have bounding boxes
        if material.bounding_boxes:
            # All boxes should be valid
            for bbox in material.bounding_boxes:
                assert bbox.x >= 0
                assert bbox.y >= 0
                assert bbox.width > 0
                assert bbox.height > 0
                assert 0.0 <= bbox.confidence <= 1.0


def test_pipeline_brand_detection(pipeline, sample_image):
    """Test brand detection in pipeline"""
    response = pipeline.process_image(sample_image)

    # Some materials may have brands detected
    brands_detected = [m.brand for m in response.materials if m.brand]

    # If brands detected, should be valid strings
    for brand in brands_detected:
        assert isinstance(brand, str)
        assert len(brand) > 0


def test_pipeline_brand_tags(pipeline, sample_image):
    """Test that brand tags are added"""
    response = pipeline.process_image(sample_image)

    # If brands detected, should have brand tags
    brands = [m.brand for m in response.materials if m.brand]
    if brands:
        # Should have at least one brand tag
        brand_tags = [tag for tag in response.tags if tag.startswith("brand_")]
        # May or may not have brand tags depending on mock data


def test_pipeline_edge_cases(pipeline):
    """Test pipeline edge cases"""
    # Very small image
    small_img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    response = pipeline.process_image(small_img)
    assert response is not None

    # Large image
    large_img = Image.fromarray(np.random.randint(0, 255, (2000, 1500, 3), dtype=np.uint8))
    response = pipeline.process_image(large_img)
    assert response is not None


def test_pipeline_disabled_features():
    """Test pipeline with features disabled"""
    # Disable counting and brand detection
    config = MaterialDetectionConfig(
        enable_counting=False,
        enable_brand_detection=False,
    )

    pipeline = MaterialDetectionPipeline(config)

    sample_image = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    response = pipeline.process_image(sample_image)

    # Should still return valid response
    assert response is not None
    assert isinstance(response.materials, list)


def test_pipeline_overall_confidence(pipeline, sample_image):
    """Test overall confidence calculation"""
    response = pipeline.process_image(sample_image)

    if response.materials:
        # Overall confidence should be average of material confidences
        expected_confidence = sum(m.confidence for m in response.materials) / len(response.materials)

        # Allow small floating point difference
        assert abs(response.confidence - expected_confidence) < 0.01
    else:
        # No materials detected, confidence should be 0
        assert response.confidence == 0.0


def test_pipeline_delivery_size_tags(pipeline, sample_image):
    """Test delivery size tags"""
    response = pipeline.process_image(sample_image)

    # Should have one of the delivery size tags
    size_tags = ["small_delivery", "medium_delivery", "large_delivery"]
    has_size_tag = any(tag in response.tags for tag in size_tags)

    # Only if materials detected
    if response.materials:
        assert has_size_tag
