"""Tests for Material Segmentation"""

import pytest
import numpy as np
from src.ai_models.volume_estimation.material_segmenter import MaterialSegmenter, MockSegmentationModel
from src.ai_models.volume_estimation.config import MaterialSegmentationConfig


@pytest.fixture
def seg_config():
    """Create segmentation config"""
    return MaterialSegmentationConfig(device="cpu")


@pytest.fixture
def material_segmenter(seg_config):
    """Create and load material segmenter"""
    segmenter = MaterialSegmenter(seg_config)
    segmenter.load_model()
    return segmenter


@pytest.fixture
def sample_image():
    """Create a sample RGB image"""
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


def test_material_segmenter_initialization(seg_config):
    """Test material segmenter initialization"""
    segmenter = MaterialSegmenter(seg_config)
    assert segmenter.config == seg_config
    assert segmenter.model is None
    assert segmenter._inference_count == 0


def test_load_model(material_segmenter):
    """Test model loading"""
    assert material_segmenter.model is not None
    assert isinstance(material_segmenter.model, MockSegmentationModel)


def test_preprocess_image(material_segmenter, sample_image):
    """Test image preprocessing"""
    preprocessed = material_segmenter.preprocess_image(sample_image)

    # Check output shape
    assert preprocessed.shape[:2] == material_segmenter.config.input_size
    assert preprocessed.dtype == np.float32


def test_segment(material_segmenter, sample_image):
    """Test material segmentation"""
    mask, material_type, metadata = material_segmenter.segment(sample_image)

    # Check mask
    assert mask.shape == sample_image.shape[:2]
    assert mask.dtype == np.uint8
    assert set(np.unique(mask)).issubset({0, 1})

    # Check material type
    assert material_type in ["gravel", "mulch", "sand", "other_material", "unknown"]

    # Check metadata
    assert "inference_time_ms" in metadata
    assert "material_confidence" in metadata
    assert "mask_coverage" in metadata
    assert metadata["inference_time_ms"] > 0


def test_identify_material(material_segmenter):
    """Test material identification"""
    # Create mock class map
    class_map = np.zeros((100, 100), dtype=np.int32)
    class_map[40:80, 40:80] = 1  # Gravel region

    # Create mock class probabilities
    class_probs = np.zeros((100, 100, 5), dtype=np.float32)
    class_probs[:, :, 0] = 0.9  # Background
    class_probs[40:80, 40:80, 0] = 0.1
    class_probs[40:80, 40:80, 1] = 0.85  # Gravel

    material_type, confidence = material_segmenter._identify_material(class_map, class_probs)

    assert material_type == "gravel"
    assert 0.0 <= confidence <= 1.0


def test_create_material_mask(material_segmenter):
    """Test material mask creation"""
    class_map = np.zeros((100, 100), dtype=np.int32)
    class_map[40:80, 40:80] = 2  # Mulch

    mask = material_segmenter._create_material_mask(class_map, "mulch")

    assert mask.shape == class_map.shape
    assert mask.dtype == np.uint8
    assert mask[50, 50] == 1  # Inside mulch region
    assert mask[10, 10] == 0  # Outside mulch region


def test_postprocess_mask(material_segmenter):
    """Test mask post-processing"""
    # Create noisy mask
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[40:80, 40:80] = 1
    # Add some noise
    mask[10:12, 10:12] = 1

    cleaned = material_segmenter._postprocess_mask(mask)

    assert cleaned.shape == mask.shape
    assert cleaned.dtype == np.uint8
    # Small noise should be removed
    assert cleaned[10, 10] == 0


def test_compute_class_distribution(material_segmenter):
    """Test class distribution computation"""
    class_map = np.zeros((100, 100), dtype=np.int32)
    class_map[0:50, :] = 1  # Half gravel

    distribution = material_segmenter._compute_class_distribution(class_map)

    assert "background" in distribution
    assert "gravel" in distribution
    assert distribution["gravel"] == 0.5
    assert distribution["background"] == 0.5


def test_get_stats(material_segmenter, sample_image):
    """Test statistics retrieval"""
    # Run some segmentations
    material_segmenter.segment(sample_image)
    material_segmenter.segment(sample_image)

    stats = material_segmenter.get_stats()

    assert stats["inference_count"] == 2
    assert stats["average_inference_time_ms"] > 0
    assert stats["model_type"] == material_segmenter.config.model_type


def test_mock_segmentation_model():
    """Test mock segmentation model"""
    model = MockSegmentationModel("deeplabv3_resnet50", 5, "cpu")

    # Create test image
    image = np.random.rand(512, 512, 3).astype(np.float32)

    class_map, class_probs = model.predict(image)

    assert class_map.shape == image.shape[:2]
    assert class_probs.shape == (*image.shape[:2], 5)
    assert class_map.dtype == np.int32
    assert class_probs.dtype == np.float32
