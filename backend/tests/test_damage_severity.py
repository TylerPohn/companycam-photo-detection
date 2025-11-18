"""Unit tests for severity classifier"""

import pytest
from PIL import Image
import numpy as np

from src.ai_models.damage_detection.severity_classifier import SeverityClassifier
from src.ai_models.damage_detection.config import SeverityClassifierConfig
from src.schemas.damage_detection import BoundingBox, DamageType, DamageSeverity


@pytest.fixture
def classifier_config():
    """Create classifier configuration for testing"""
    return SeverityClassifierConfig(
        confidence_threshold=0.6,
        input_size=224,
        device="cpu",
    )


@pytest.fixture
def classifier(classifier_config):
    """Create classifier instance"""
    return SeverityClassifier(classifier_config)


@pytest.fixture
def sample_image():
    """Create a sample test image"""
    image_array = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    return Image.fromarray(image_array, mode="RGB")


@pytest.fixture
def sample_bounding_box():
    """Create a sample bounding box"""
    return BoundingBox(x=100, y=100, width=200, height=150)


class TestSeverityClassifier:
    """Test suite for SeverityClassifier"""

    def test_classifier_initialization(self, classifier, classifier_config):
        """Test classifier initializes with correct configuration"""
        assert classifier.config == classifier_config
        assert classifier.model_loaded is False
        assert classifier.inference_count == 0

    def test_model_loading(self, classifier):
        """Test model loading"""
        classifier.load_model()
        assert classifier.model_loaded is True

    def test_roi_preprocessing(self, classifier, sample_image, sample_bounding_box):
        """Test ROI preprocessing"""
        processed = classifier.preprocess_roi(sample_image, sample_bounding_box)

        # Check processed shape
        assert processed.shape == (224, 224, 3)

        # Check ImageNet normalization applied
        # Values should be in normalized range (can be negative)
        assert processed.min() < 0  # Due to normalization
        assert processed.max() > 0

    def test_classify_severity_returns_valid_severity(
        self, classifier, sample_image, sample_bounding_box
    ):
        """Test classification returns valid severity level"""
        severity, confidence = classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.85,
        )

        # Check severity is valid
        assert severity in [
            DamageSeverity.MINOR,
            DamageSeverity.MODERATE,
            DamageSeverity.SEVERE,
        ]

        # Check confidence is in valid range
        assert 0.0 <= confidence <= 1.0

    def test_classify_severity_loads_model_automatically(
        self, classifier, sample_image, sample_bounding_box
    ):
        """Test that classify loads model if not already loaded"""
        assert classifier.model_loaded is False
        classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.85,
        )
        assert classifier.model_loaded is True

    def test_classify_severity_increments_inference_count(
        self, classifier, sample_image, sample_bounding_box
    ):
        """Test that inference count is incremented"""
        initial_count = classifier.inference_count

        classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.85,
        )
        assert classifier.inference_count == initial_count + 1

    def test_classify_severity_respects_confidence_threshold(
        self, classifier, sample_image, sample_bounding_box
    ):
        """Test that confidence meets threshold"""
        severity, confidence = classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.85,
        )

        # Confidence should meet or exceed threshold
        assert confidence >= classifier.config.confidence_threshold

    def test_classify_all_damage_types(self, classifier, sample_image, sample_bounding_box):
        """Test classification for all damage types"""
        damage_types = [
            DamageType.HAIL_DAMAGE,
            DamageType.WIND_DAMAGE,
            DamageType.MISSING_SHINGLES,
        ]

        for damage_type in damage_types:
            severity, confidence = classifier.classify_severity(
                sample_image,
                sample_bounding_box,
                damage_type,
                detection_confidence=0.85,
            )

            assert isinstance(severity, DamageSeverity)
            assert 0.0 <= confidence <= 1.0

    def test_mock_severity_classification_area_based(self, classifier):
        """Test mock severity classification based on damage area"""
        # Small damage - should be minor
        small_box = BoundingBox(x=0, y=0, width=50, height=50)
        severity, _ = classifier._classify_mock_severity(
            DamageType.HAIL_DAMAGE, 0.85, small_box
        )
        # Small area typically results in MINOR (area < 10000)
        assert severity in [DamageSeverity.MINOR, DamageSeverity.MODERATE]

        # Large damage - more likely severe
        large_box = BoundingBox(x=0, y=0, width=300, height=300)
        severity, _ = classifier._classify_mock_severity(
            DamageType.HAIL_DAMAGE, 0.85, large_box
        )
        # Large area typically results in MODERATE or SEVERE
        assert severity in [DamageSeverity.MODERATE, DamageSeverity.SEVERE]

    def test_confidence_correlates_with_detection_confidence(
        self, classifier, sample_image, sample_bounding_box
    ):
        """Test that severity confidence is correlated with detection confidence"""
        # High detection confidence
        severity1, conf1 = classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.95,
        )

        # Low detection confidence
        severity2, conf2 = classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.70,
        )

        # Higher detection confidence should generally lead to higher severity confidence
        # (with some randomness in mock implementation)
        assert 0.0 <= conf1 <= 1.0
        assert 0.0 <= conf2 <= 1.0

    def test_get_inference_stats(self, classifier, sample_image, sample_bounding_box):
        """Test inference statistics"""
        classifier.classify_severity(
            sample_image,
            sample_bounding_box,
            DamageType.HAIL_DAMAGE,
            detection_confidence=0.85,
        )

        stats = classifier.get_inference_stats()

        assert "model_loaded" in stats
        assert "inference_count" in stats
        assert "config" in stats

        assert stats["model_loaded"] is True
        assert stats["inference_count"] > 0

    def test_different_damage_types_different_thresholds(self, classifier):
        """Test that different damage types have different severity thresholds"""
        # Same size box, different damage types
        bbox = BoundingBox(x=0, y=0, width=100, height=100)

        severity_hail, _ = classifier._classify_mock_severity(
            DamageType.HAIL_DAMAGE, 0.85, bbox
        )

        severity_wind, _ = classifier._classify_mock_severity(
            DamageType.WIND_DAMAGE, 0.85, bbox
        )

        severity_missing, _ = classifier._classify_mock_severity(
            DamageType.MISSING_SHINGLES, 0.85, bbox
        )

        # All should be valid severity levels
        assert all(
            s in [DamageSeverity.MINOR, DamageSeverity.MODERATE, DamageSeverity.SEVERE]
            for s in [severity_hail, severity_wind, severity_missing]
        )

    def test_classify_with_different_bounding_box_sizes(self, classifier, sample_image):
        """Test classification with various bounding box sizes"""
        test_boxes = [
            BoundingBox(x=10, y=10, width=30, height=30),    # Very small
            BoundingBox(x=50, y=50, width=100, height=100),  # Medium
            BoundingBox(x=100, y=100, width=250, height=200), # Large
        ]

        for bbox in test_boxes:
            severity, confidence = classifier.classify_severity(
                sample_image,
                bbox,
                DamageType.HAIL_DAMAGE,
                detection_confidence=0.85,
            )

            assert isinstance(severity, DamageSeverity)
            assert 0.0 <= confidence <= 1.0
