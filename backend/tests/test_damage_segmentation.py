"""Unit tests for U-Net damage segmenter"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.damage_detection.segmenter import DamageSegmenter
from src.ai_models.damage_detection.config import SegmenterConfig
from src.schemas.damage_detection import BoundingBox


@pytest.fixture
def segmenter_config():
    """Create segmenter configuration for testing"""
    return SegmenterConfig(
        confidence_threshold=0.5,
        input_size=512,
        device="cpu",
    )


@pytest.fixture
def segmenter(segmenter_config):
    """Create segmenter instance"""
    return DamageSegmenter(segmenter_config)


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    # Create 640x480 RGB image
    image_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(image_array, mode="RGB")


@pytest.fixture
def sample_bounding_box():
    """Create a sample bounding box"""
    return BoundingBox(x=100, y=100, width=200, height=150)


class TestDamageSegmenter:
    """Test suite for DamageSegmenter"""

    def test_segmenter_initialization(self, segmenter, segmenter_config):
        """Test segmenter initializes with correct configuration"""
        assert segmenter.config == segmenter_config
        assert segmenter.model_loaded is False
        assert segmenter.inference_count == 0

    def test_model_loading(self, segmenter):
        """Test model loading"""
        segmenter.load_model()
        assert segmenter.model_loaded is True

    def test_roi_preprocessing(self, segmenter, sample_image, sample_bounding_box):
        """Test ROI preprocessing"""
        processed, original_size = segmenter.preprocess_roi(
            sample_image, sample_bounding_box
        )

        # Check processed image has correct shape
        assert processed.shape == (512, 512, 3)

        # Check normalization
        assert processed.min() >= 0.0
        assert processed.max() <= 1.0

        # Check original size matches bounding box
        assert original_size == (sample_bounding_box.width, sample_bounding_box.height)

    def test_segment_returns_mask_and_percentage(
        self, segmenter, sample_image, sample_bounding_box
    ):
        """Test segmentation returns mask and area percentage"""
        mask, area_percentage = segmenter.segment(sample_image, sample_bounding_box)

        # Check mask is PIL Image
        assert isinstance(mask, Image.Image)
        assert mask.mode == "L"  # Grayscale

        # Check mask size matches bounding box
        assert mask.size == (sample_bounding_box.width, sample_bounding_box.height)

        # Check area percentage is valid
        assert 0.0 <= area_percentage <= 100.0

    def test_segment_loads_model_automatically(
        self, segmenter, sample_image, sample_bounding_box
    ):
        """Test that segment loads model if not already loaded"""
        assert segmenter.model_loaded is False
        segmenter.segment(sample_image, sample_bounding_box)
        assert segmenter.model_loaded is True

    def test_segment_increments_inference_count(
        self, segmenter, sample_image, sample_bounding_box
    ):
        """Test that inference count is incremented"""
        initial_count = segmenter.inference_count

        segmenter.segment(sample_image, sample_bounding_box)
        assert segmenter.inference_count == initial_count + 1

        segmenter.segment(sample_image, sample_bounding_box)
        assert segmenter.inference_count == initial_count + 2

    def test_mask_to_bytes_conversion(self, segmenter, sample_image, sample_bounding_box):
        """Test mask to bytes conversion"""
        mask, _ = segmenter.segment(sample_image, sample_bounding_box)
        mask_bytes = segmenter.mask_to_bytes(mask)

        # Check bytes are returned
        assert isinstance(mask_bytes, bytes)
        assert len(mask_bytes) > 0

    def test_mask_to_bytes_png_format(self, segmenter, sample_image, sample_bounding_box):
        """Test mask to bytes uses PNG format"""
        mask, _ = segmenter.segment(sample_image, sample_bounding_box)
        mask_bytes = segmenter.mask_to_bytes(mask, format="PNG")

        # Check PNG signature
        assert mask_bytes[:8] == b'\x89PNG\r\n\x1a\n'

    def test_get_inference_stats(self, segmenter, sample_image, sample_bounding_box):
        """Test inference statistics"""
        segmenter.segment(sample_image, sample_bounding_box)
        stats = segmenter.get_inference_stats()

        assert "model_loaded" in stats
        assert "inference_count" in stats
        assert "config" in stats

        assert stats["model_loaded"] is True
        assert stats["inference_count"] > 0

    def test_segment_with_different_bounding_box_sizes(self, segmenter, sample_image):
        """Test segmentation with various bounding box sizes"""
        test_boxes = [
            BoundingBox(x=10, y=10, width=50, height=50),    # Small
            BoundingBox(x=50, y=50, width=100, height=100),  # Medium
            BoundingBox(x=100, y=100, width=200, height=150), # Large
        ]

        for bbox in test_boxes:
            mask, area_pct = segmenter.segment(sample_image, bbox)

            assert isinstance(mask, Image.Image)
            assert mask.size == (bbox.width, bbox.height)
            assert 0.0 <= area_pct <= 100.0

    def test_mock_mask_generation(self, segmenter):
        """Test mock segmentation mask generation"""
        width, height = 200, 150
        mask, area_percentage = segmenter._generate_mock_segmentation_mask(width, height)

        # Check mask properties
        assert isinstance(mask, Image.Image)
        assert mask.size == (width, height)
        assert mask.mode == "L"

        # Check area percentage is reasonable
        assert 0.0 < area_percentage <= 100.0

    def test_mask_binary_values(self, segmenter, sample_image, sample_bounding_box):
        """Test that mask contains binary values (0 or 255)"""
        mask, _ = segmenter.segment(sample_image, sample_bounding_box)

        # Convert to numpy array
        mask_array = np.array(mask)

        # Check values are binary
        unique_values = np.unique(mask_array)
        assert all(v in [0, 255] for v in unique_values)

    def test_segment_edge_cases(self, segmenter, sample_image):
        """Test segmentation with edge case bounding boxes"""
        # Very small bounding box
        small_box = BoundingBox(x=0, y=0, width=10, height=10)
        mask1, area1 = segmenter.segment(sample_image, small_box)
        assert isinstance(mask1, Image.Image)
        assert 0.0 <= area1 <= 100.0

        # Bounding box at image edge
        edge_box = BoundingBox(x=0, y=0, width=100, height=100)
        mask2, area2 = segmenter.segment(sample_image, edge_box)
        assert isinstance(mask2, Image.Image)
        assert 0.0 <= area2 <= 100.0
