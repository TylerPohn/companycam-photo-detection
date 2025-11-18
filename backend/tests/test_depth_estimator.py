"""Tests for Depth Estimator"""

import pytest
import numpy as np
from src.ai_models.volume_estimation.depth_estimator import DepthEstimator, MockDepthModel
from src.ai_models.volume_estimation.config import DepthEstimationConfig


@pytest.fixture
def depth_config():
    """Create depth estimation config"""
    return DepthEstimationConfig(device="cpu")


@pytest.fixture
def depth_estimator(depth_config):
    """Create and load depth estimator"""
    estimator = DepthEstimator(depth_config)
    estimator.load_model()
    return estimator


@pytest.fixture
def sample_image():
    """Create a sample RGB image"""
    # 640x480 RGB image
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


def test_depth_estimator_initialization(depth_config):
    """Test depth estimator initialization"""
    estimator = DepthEstimator(depth_config)
    assert estimator.config == depth_config
    assert estimator.model is None
    assert estimator._inference_count == 0


def test_load_model(depth_estimator):
    """Test model loading"""
    assert depth_estimator.model is not None
    assert isinstance(depth_estimator.model, MockDepthModel)


def test_preprocess_image(depth_estimator, sample_image):
    """Test image preprocessing"""
    preprocessed = depth_estimator.preprocess_image(sample_image)

    # Check output shape (should be resized to input_size)
    assert preprocessed.shape[0] <= depth_estimator.config.input_size
    assert preprocessed.shape[1] <= depth_estimator.config.input_size

    # Check normalization
    assert preprocessed.dtype == np.float32


def test_estimate_depth(depth_estimator, sample_image):
    """Test depth estimation"""
    depth_map, metadata = depth_estimator.estimate_depth(sample_image)

    # Check depth map
    assert depth_map.shape == sample_image.shape[:2]
    assert depth_map.dtype == np.float32
    assert depth_map.min() >= 0.0
    assert depth_map.max() <= 1.0

    # Check metadata
    assert "inference_time_ms" in metadata
    assert "confidence" in metadata
    assert "depth_range" in metadata
    assert metadata["inference_time_ms"] > 0


def test_normalize_depth_map(depth_estimator):
    """Test depth map normalization"""
    # Create test depth map
    depth_map = np.random.rand(100, 100).astype(np.float32) * 100

    normalized = depth_estimator._normalize_depth_map(depth_map)

    assert normalized.min() >= 0.0
    assert normalized.max() <= 1.0
    assert normalized.shape == depth_map.shape


def test_estimate_confidence(depth_estimator):
    """Test confidence estimation"""
    # Good depth map - medium variance
    good_depth = np.random.rand(100, 100).astype(np.float32) * 0.3 + 0.35
    confidence_good = depth_estimator._estimate_confidence(good_depth)
    assert 0.0 <= confidence_good <= 1.0
    assert confidence_good > 0.7  # Should have good confidence

    # Flat depth map - low variance
    flat_depth = np.ones((100, 100), dtype=np.float32) * 0.5
    confidence_flat = depth_estimator._estimate_confidence(flat_depth)
    assert confidence_flat < confidence_good  # Should have lower confidence


def test_create_depth_visualization(depth_estimator, sample_image):
    """Test depth map visualization"""
    depth_map, _ = depth_estimator.estimate_depth(sample_image)

    visualization = depth_estimator.create_depth_visualization(depth_map)

    # Check visualization
    assert visualization.shape == (*depth_map.shape, 3)
    assert visualization.dtype == np.uint8


def test_get_stats(depth_estimator, sample_image):
    """Test statistics retrieval"""
    # Run some inferences
    depth_estimator.estimate_depth(sample_image)
    depth_estimator.estimate_depth(sample_image)

    stats = depth_estimator.get_stats()

    assert stats["inference_count"] == 2
    assert stats["average_inference_time_ms"] > 0
    assert stats["model_type"] == depth_estimator.config.model_type


def test_mock_depth_model():
    """Test mock depth model"""
    model = MockDepthModel("DPT_Large", "cpu")

    # Create test image
    image = np.random.rand(256, 256, 3).astype(np.float32)

    depth_map = model.predict(image)

    assert depth_map.shape == image.shape[:2]
    assert depth_map.dtype == np.float32
    assert depth_map.min() >= 0.0
