"""Tests for Volume Estimation Pipeline"""

import pytest
import numpy as np
from PIL import Image
import io
from src.ai_models.volume_estimation.pipeline import VolumeEstimationPipeline
from src.ai_models.volume_estimation.config import VolumeEstimationConfig


@pytest.fixture
def pipeline_config():
    """Create pipeline config"""
    return VolumeEstimationConfig()


@pytest.fixture
def pipeline(pipeline_config):
    """Create and load pipeline"""
    p = VolumeEstimationPipeline(pipeline_config)
    p.load_models()
    return p


@pytest.fixture
def sample_image():
    """Create a sample RGB image"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


def test_pipeline_initialization(pipeline_config):
    """Test pipeline initialization"""
    pipeline = VolumeEstimationPipeline(pipeline_config)

    assert pipeline.config == pipeline_config
    assert pipeline.depth_estimator is not None
    assert pipeline.material_segmenter is not None
    assert pipeline.scale_detector is not None
    assert pipeline.volume_calculator is not None
    assert pipeline._models_loaded is False
    assert pipeline._inference_count == 0


def test_load_models(pipeline):
    """Test model loading"""
    assert pipeline._models_loaded is True
    assert pipeline.depth_estimator.model is not None
    assert pipeline.material_segmenter.model is not None
    assert pipeline.scale_detector.model is not None


def test_estimate_volume(pipeline, sample_image):
    """Test end-to-end volume estimation"""
    result = pipeline.estimate_volume(sample_image, save_depth_map=True)

    # Check all required fields
    assert "material" in result
    assert "estimated_volume" in result
    assert "unit" in result
    assert "confidence" in result
    assert "requires_confirmation" in result
    assert "volume_range" in result
    assert "depth_map" in result
    assert "scale_reference" in result
    assert "calculation_method" in result
    assert "processing_time_ms" in result
    assert "model_version" in result
    assert "confidence_breakdown" in result
    assert "component_timings_ms" in result

    # Check value ranges
    assert result["estimated_volume"] >= 0.0
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["processing_time_ms"] > 0.0

    # Check volume range
    assert result["volume_range"]["min"] >= 0.0
    assert result["volume_range"]["max"] >= result["volume_range"]["min"]

    # Check confidence breakdown
    breakdown = result["confidence_breakdown"]
    assert "depth_estimation" in breakdown
    assert "material_detection" in breakdown
    assert "scale_detection" in breakdown
    for key, value in breakdown.items():
        assert 0.0 <= value <= 1.0

    # Check component timings
    timings = result["component_timings_ms"]
    assert timings["depth_estimation"] > 0
    assert timings["material_segmentation"] > 0
    assert timings["scale_detection"] > 0
    assert timings["volume_calculation"] > 0


def test_estimate_volume_without_depth_map(pipeline, sample_image):
    """Test volume estimation without saving depth map"""
    result = pipeline.estimate_volume(sample_image, save_depth_map=False)

    assert "estimated_volume" in result
    # depth_map can still be a placeholder
    assert "depth_map" in result


def test_estimate_volume_models_not_loaded():
    """Test estimation fails if models not loaded"""
    pipeline = VolumeEstimationPipeline()

    image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    with pytest.raises(RuntimeError, match="Models not loaded"):
        pipeline.estimate_volume(image)


def test_calculate_confidence_breakdown(pipeline):
    """Test confidence breakdown calculation"""
    depth_metadata = {"confidence": 0.88}
    seg_metadata = {"material_confidence": 0.92}
    scale_metadata = {"has_scale_reference": True}
    volume_metadata = {}

    breakdown = pipeline._calculate_confidence_breakdown(
        depth_metadata,
        seg_metadata,
        scale_metadata,
        volume_metadata
    )

    assert "depth_estimation" in breakdown
    assert "material_detection" in breakdown
    assert "scale_detection" in breakdown
    assert breakdown["depth_estimation"] == 0.88
    assert breakdown["material_detection"] == 0.92


def test_calculate_overall_confidence(pipeline):
    """Test overall confidence calculation"""
    breakdown = {
        "depth_estimation": 0.88,
        "material_detection": 0.92,
        "scale_detection": 0.75
    }

    overall = pipeline._calculate_overall_confidence(breakdown)

    assert 0.0 <= overall <= 1.0
    # Should be weighted average
    assert 0.80 <= overall <= 0.90


def test_format_scale_reference(pipeline):
    """Test scale reference formatting"""
    # With reference
    scale_reference = {
        "type": "person",
        "confidence": 0.85,
        "estimated_height_cm": 170.0,
        "bbox": (100, 100, 150, 300)
    }

    formatted = pipeline._format_scale_reference(scale_reference)

    assert formatted is not None
    assert formatted["type"] == "person"
    assert formatted["confidence"] == 0.85
    assert formatted["estimated_height_cm"] == 170.0

    # Without reference
    formatted_none = pipeline._format_scale_reference(None)
    assert formatted_none is None


def test_estimate_volume_from_file(pipeline, tmp_path):
    """Test estimating volume from file"""
    # Create temporary image file
    image = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    image_path = tmp_path / "test_image.jpg"
    image.save(image_path)

    result = pipeline.estimate_volume_from_file(str(image_path))

    assert "estimated_volume" in result
    assert result["processing_time_ms"] > 0


def test_estimate_volume_from_bytes(pipeline):
    """Test estimating volume from bytes"""
    # Create image bytes
    image = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    image_bytes = buffer.getvalue()

    result = pipeline.estimate_volume_from_bytes(image_bytes)

    assert "estimated_volume" in result
    assert result["processing_time_ms"] > 0


def test_get_stats(pipeline, sample_image):
    """Test pipeline statistics"""
    # Run some inferences
    pipeline.estimate_volume(sample_image)
    pipeline.estimate_volume(sample_image)

    stats = pipeline.get_stats()

    assert stats["inference_count"] == 2
    assert stats["average_processing_time_ms"] > 0
    assert stats["models_loaded"] is True
    assert stats["model_version"] == pipeline.config.model_version
    assert "components" in stats
    assert "depth_estimator" in stats["components"]


def test_multiple_estimations(pipeline, sample_image):
    """Test multiple consecutive estimations"""
    results = []

    for _ in range(3):
        result = pipeline.estimate_volume(sample_image)
        results.append(result)

    # All should succeed
    assert len(results) == 3
    for result in results:
        assert result["estimated_volume"] >= 0.0

    # Stats should reflect 3 inferences
    stats = pipeline.get_stats()
    assert stats["inference_count"] == 3


def test_requires_confirmation_flag(pipeline, sample_image):
    """Test requires_confirmation flag based on confidence"""
    result = pipeline.estimate_volume(sample_image)

    # Check consistency
    if result["confidence"] < pipeline.config.confidence.low_confidence_threshold:
        assert result["requires_confirmation"] is True
    else:
        assert result["requires_confirmation"] is False
