"""Tests for material quantity validation"""

import pytest

from src.ai_models.material_detection import MaterialValidator, ValidatorConfig
from src.schemas.material_detection import AlertType


@pytest.fixture
def validator_config():
    """Create validator config for testing"""
    return ValidatorConfig(
        underage_threshold_pct=5.0,
        overage_threshold_pct=5.0,
        enable_alerts=True,
    )


@pytest.fixture
def validator(validator_config):
    """Create material validator instance"""
    return MaterialValidator(validator_config)


def test_validator_initialization(validator, validator_config):
    """Test validator initializes correctly"""
    assert validator.config == validator_config


def test_validator_exact_match(validator):
    """Test validation with exact quantity match"""
    alert = validator.validate_quantity(
        detected_count=36,
        expected_count=36,
        unit="bundles",
    )

    # Should have no alert
    assert alert is None


def test_validator_no_expected_count(validator):
    """Test validation with no expected count"""
    alert = validator.validate_quantity(
        detected_count=25,
        expected_count=None,
        unit="sheets",
    )

    # Should have no alert when no expected count
    assert alert is None


def test_validator_underage_alert(validator):
    """Test underage alert generation"""
    alert = validator.validate_quantity(
        detected_count=24,
        expected_count=25,
        unit="sheets",
    )

    # Should generate underage alert (4% underage)
    assert alert is None  # 4% is below 5% threshold

    # Test with significant underage
    alert = validator.validate_quantity(
        detected_count=20,
        expected_count=25,
        unit="sheets",
    )

    # Should generate alert (20% underage)
    assert alert is not None
    assert alert.type == AlertType.UNDERAGE
    assert "Expected 25 sheets but detected 20 sheets" in alert.message
    assert alert.variance_percentage < 0  # Negative variance


def test_validator_overage_alert(validator):
    """Test overage alert generation"""
    alert = validator.validate_quantity(
        detected_count=26,
        expected_count=25,
        unit="sheets",
    )

    # Should generate overage alert (4% overage)
    assert alert is None  # 4% is below 5% threshold

    # Test with significant overage
    alert = validator.validate_quantity(
        detected_count=30,
        expected_count=25,
        unit="sheets",
    )

    # Should generate alert (20% overage)
    assert alert is not None
    assert alert.type == AlertType.OVERAGE
    assert "Expected 25 sheets but detected 30 sheets" in alert.message
    assert alert.variance_percentage > 0  # Positive variance


def test_validator_threshold_boundaries(validator):
    """Test validation at threshold boundaries"""
    # Exactly at threshold (5%)
    alert = validator.validate_quantity(
        detected_count=95,
        expected_count=100,
        unit="bundles",
    )

    # 5% underage - should trigger alert
    assert alert is not None
    assert alert.type == AlertType.UNDERAGE

    # Just below threshold (4.9%)
    alert = validator.validate_quantity(
        detected_count=96,
        expected_count=100,
        unit="bundles",
    )

    # Should not trigger alert
    assert alert is None


def test_validator_variance_percentage_calculation(validator):
    """Test variance percentage calculation"""
    # Test underage
    variance_pct = validator.calculate_variance_percentage(
        detected_count=20,
        expected_count=25,
    )
    assert variance_pct == -20.0

    # Test overage
    variance_pct = validator.calculate_variance_percentage(
        detected_count=30,
        expected_count=25,
    )
    assert variance_pct == 20.0

    # Test exact match
    variance_pct = validator.calculate_variance_percentage(
        detected_count=25,
        expected_count=25,
    )
    assert variance_pct == 0.0


def test_validator_variance_percentage_zero_expected(validator):
    """Test variance calculation with zero expected count"""
    variance_pct = validator.calculate_variance_percentage(
        detected_count=10,
        expected_count=0,
    )
    assert variance_pct == 0.0


def test_validator_is_within_tolerance(validator):
    """Test tolerance checking"""
    # Within tolerance
    assert validator.is_within_tolerance(25, 25) is True
    assert validator.is_within_tolerance(24, 25) is True  # 4% under
    assert validator.is_within_tolerance(26, 25) is True  # 4% over

    # Outside tolerance
    assert validator.is_within_tolerance(20, 25) is False  # 20% under
    assert validator.is_within_tolerance(30, 25) is False  # 20% over


def test_validator_batch_validation(validator):
    """Test batch validation"""
    detections = [
        (36, 36, "bundles"),  # Exact match
        (24, 25, "sheets"),   # Minor underage (4%)
        (20, 25, "sheets"),   # Significant underage (20%)
        (30, 25, "bags"),     # Significant overage (20%)
    ]

    alerts = validator.validate_batch(detections)

    # Should have 4 results
    assert len(alerts) == 4

    # First two should have no alert
    assert alerts[0] is None
    assert alerts[1] is None

    # Third should have underage alert
    assert alerts[2] is not None
    assert alerts[2].type == AlertType.UNDERAGE

    # Fourth should have overage alert
    assert alerts[3] is not None
    assert alerts[3].type == AlertType.OVERAGE


def test_validator_custom_thresholds():
    """Test validator with custom thresholds"""
    # Strict thresholds (2%)
    strict_validator = MaterialValidator(
        ValidatorConfig(
            underage_threshold_pct=2.0,
            overage_threshold_pct=2.0,
        )
    )

    # 3% underage should trigger alert
    alert = strict_validator.validate_quantity(
        detected_count=97,
        expected_count=100,
        unit="bundles",
    )
    assert alert is not None

    # Lenient thresholds (10%)
    lenient_validator = MaterialValidator(
        ValidatorConfig(
            underage_threshold_pct=10.0,
            overage_threshold_pct=10.0,
        )
    )

    # 5% underage should not trigger alert
    alert = lenient_validator.validate_quantity(
        detected_count=95,
        expected_count=100,
        unit="bundles",
    )
    assert alert is None


def test_validator_alerts_disabled():
    """Test validator with alerts disabled"""
    validator = MaterialValidator(
        ValidatorConfig(enable_alerts=False)
    )

    # Even with significant variance, alerts are still generated
    # (enable_alerts doesn't disable generation, just a config flag)
    alert = validator.validate_quantity(
        detected_count=20,
        expected_count=25,
        unit="sheets",
    )

    # Alert should still be generated
    assert alert is not None


def test_validator_large_quantities(validator):
    """Test validation with large quantities"""
    # Test with 1000 units
    alert = validator.validate_quantity(
        detected_count=950,
        expected_count=1000,
        unit="bundles",
    )

    # 5% underage should trigger
    assert alert is not None
    assert alert.type == AlertType.UNDERAGE


def test_validator_small_quantities(validator):
    """Test validation with small quantities"""
    # Test with 5 units
    alert = validator.validate_quantity(
        detected_count=4,
        expected_count=5,
        unit="sheets",
    )

    # 20% underage should trigger
    assert alert is not None
    assert alert.type == AlertType.UNDERAGE


def test_validator_alert_messages(validator):
    """Test alert message formatting"""
    # Underage alert
    alert = validator.validate_quantity(
        detected_count=20,
        expected_count=25,
        unit="sheets",
    )

    assert "Expected 25 sheets" in alert.message
    assert "detected 20 sheets" in alert.message

    # Overage alert
    alert = validator.validate_quantity(
        detected_count=30,
        expected_count=25,
        unit="bundles",
    )

    assert "Expected 25 bundles" in alert.message
    assert "detected 30 bundles" in alert.message


def test_validator_zero_detected(validator):
    """Test validation with zero detected count"""
    alert = validator.validate_quantity(
        detected_count=0,
        expected_count=25,
        unit="sheets",
    )

    # 100% underage should trigger
    assert alert is not None
    assert alert.type == AlertType.UNDERAGE
    assert alert.variance_percentage == -100.0
