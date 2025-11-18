"""Tests for Volume Calculator"""

import pytest
import numpy as np
from src.ai_models.volume_estimation.volume_calculator import VolumeCalculator
from src.ai_models.volume_estimation.config import VolumeCalculationConfig


@pytest.fixture
def volume_config():
    """Create volume calculation config"""
    return VolumeCalculationConfig()


@pytest.fixture
def volume_calculator(volume_config):
    """Create volume calculator"""
    return VolumeCalculator(volume_config)


@pytest.fixture
def sample_depth_map():
    """Create a sample depth map"""
    depth_map = np.zeros((480, 640), dtype=np.float32)
    # Create a pile in the center-bottom
    for y in range(300, 450):
        for x in range(200, 440):
            # Gaussian-like pile
            dist_from_center = np.sqrt((x - 320)**2 + (y - 375)**2)
            height = max(0, 1.0 - dist_from_center / 150)
            depth_map[y, x] = height * 0.5
    return depth_map


@pytest.fixture
def sample_mask():
    """Create a sample material mask"""
    mask = np.zeros((480, 640), dtype=np.uint8)
    mask[300:450, 200:440] = 1  # Material region
    return mask


@pytest.fixture
def scale_reference():
    """Create a sample scale reference"""
    return {
        "type": "person",
        "confidence": 0.85,
        "estimated_height_cm": 170.0,
        "pixels_per_cm": 2.0,
        "pixel_dimension": 200,
        "dimension_type": "height"
    }


def test_volume_calculator_initialization(volume_config):
    """Test volume calculator initialization"""
    calculator = VolumeCalculator(volume_config)
    assert calculator.config == volume_config


def test_calculate_volume_with_reference(
    volume_calculator, sample_depth_map, sample_mask, scale_reference
):
    """Test volume calculation with scale reference"""
    volume, metadata = volume_calculator.calculate_volume(
        sample_depth_map,
        sample_mask,
        scale_reference,
        "gravel"
    )

    assert volume >= 0.0
    assert "method" in metadata
    assert "volume_cubic_meters" in metadata
    assert "volume_cubic_yards" in metadata
    assert "material_pixels" in metadata
    assert metadata["has_scale_reference"] is True
    assert "person" in metadata["method"]


def test_calculate_volume_without_reference(
    volume_calculator, sample_depth_map, sample_mask
):
    """Test volume calculation without scale reference"""
    volume, metadata = volume_calculator.calculate_volume(
        sample_depth_map,
        sample_mask,
        None,
        "gravel"
    )

    assert volume >= 0.0
    assert metadata["has_scale_reference"] is False
    assert "heuristic" in metadata["method"]


def test_calculate_volume_insufficient_area(volume_calculator):
    """Test volume calculation with insufficient material area"""
    # Very small depth map and mask
    depth_map = np.random.rand(100, 100).astype(np.float32)
    mask = np.zeros((100, 100), dtype=np.uint8)
    mask[0:5, 0:5] = 1  # Only 25 pixels

    volume, metadata = volume_calculator.calculate_volume(
        depth_map,
        mask,
        None,
        "gravel"
    )

    assert volume == 0.0
    assert "error" in metadata


def test_extract_material_depth(volume_calculator, sample_depth_map, sample_mask):
    """Test material depth extraction"""
    material_depth = volume_calculator._extract_material_depth(
        sample_depth_map,
        sample_mask
    )

    assert material_depth.shape == sample_depth_map.shape
    assert material_depth.dtype == np.float32
    # Non-material pixels should be zero
    assert material_depth[0, 0] == 0.0


def test_apply_scale_reference(volume_calculator, sample_depth_map, sample_mask, scale_reference):
    """Test applying scale reference"""
    material_depth = volume_calculator._extract_material_depth(sample_depth_map, sample_mask)

    real_world_depth, scale_factor = volume_calculator._apply_scale_reference(
        material_depth,
        scale_reference,
        sample_depth_map,
        sample_mask
    )

    assert real_world_depth.shape == material_depth.shape
    assert scale_factor > 0.0


def test_apply_heuristic_scale(volume_calculator, sample_depth_map):
    """Test applying heuristic scale"""
    real_world_depth, scale_factor = volume_calculator._apply_heuristic_scale(
        sample_depth_map,
        sample_depth_map.shape
    )

    assert real_world_depth.shape == sample_depth_map.shape
    assert scale_factor > 0.0


def test_integrate_volume(volume_calculator, sample_mask):
    """Test volume integration"""
    # Create simple depth map
    real_world_depth = np.ones_like(sample_mask, dtype=np.float32) * 50.0  # 50 cm
    scale_factor = 1.0  # 1 cm per pixel

    volume_m3 = volume_calculator._integrate_volume(
        real_world_depth,
        sample_mask,
        scale_factor
    )

    assert volume_m3 > 0.0


def test_convert_units(volume_calculator):
    """Test unit conversion"""
    volume_m3 = 1.0

    # Test conversion to cubic yards
    volume_yards = volume_calculator._convert_units(volume_m3, "cubic_yards")
    assert volume_yards > 1.0  # 1 m³ > 1 yd³

    # Test conversion to cubic feet
    volume_feet = volume_calculator._convert_units(volume_m3, "cubic_feet")
    assert volume_feet > volume_m3  # 1 m³ >> 1 ft³

    # Test unknown unit
    volume_unknown = volume_calculator._convert_units(volume_m3, "unknown_unit")
    assert volume_unknown == volume_m3  # Should return original


def test_calculate_volume_range_with_reference(volume_calculator, scale_reference):
    """Test volume range calculation with reference"""
    volume = 2.5
    confidence = 0.85

    volume_range = volume_calculator.calculate_volume_range(
        volume,
        confidence,
        scale_reference
    )

    assert "min" in volume_range
    assert "max" in volume_range
    assert volume_range["min"] < volume
    assert volume_range["max"] > volume
    assert volume_range["min"] >= 0.0


def test_calculate_volume_range_without_reference(volume_calculator):
    """Test volume range calculation without reference"""
    volume = 2.5
    confidence = 0.6

    volume_range = volume_calculator.calculate_volume_range(
        volume,
        confidence,
        None
    )

    # Should have wider range without reference
    assert volume_range["max"] - volume_range["min"] > 1.0


def test_calculate_volume_range_low_confidence(volume_calculator):
    """Test volume range with low confidence"""
    volume = 2.5
    confidence_low = 0.4
    confidence_high = 0.9

    range_low = volume_calculator.calculate_volume_range(volume, confidence_low, None)
    range_high = volume_calculator.calculate_volume_range(volume, confidence_high, None)

    # Low confidence should give wider range
    width_low = range_low["max"] - range_low["min"]
    width_high = range_high["max"] - range_high["min"]
    assert width_low > width_high
