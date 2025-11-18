"""Material quantity validation logic for comparing detected vs. expected quantities"""

import logging
from typing import Optional

from .config import ValidatorConfig
from src.schemas.material_detection import QuantityAlert, AlertType

logger = logging.getLogger(__name__)


class MaterialValidator:
    """
    Validates detected material quantities against expected values.

    Generates alerts for significant discrepancies.
    """

    def __init__(self, config: Optional[ValidatorConfig] = None):
        self.config = config or ValidatorConfig()
        logger.info(
            f"Initializing MaterialValidator "
            f"(underage: {self.config.underage_threshold_pct}%, "
            f"overage: {self.config.overage_threshold_pct}%)"
        )

    def validate_quantity(
        self,
        detected_count: int,
        expected_count: Optional[int],
        unit: str,
    ) -> Optional[QuantityAlert]:
        """
        Validate detected quantity against expected quantity.

        Args:
            detected_count: Number of units detected
            expected_count: Expected number of units (None if not provided)
            unit: Unit of measurement (e.g., 'bundles', 'sheets')

        Returns:
            QuantityAlert if discrepancy detected, None otherwise
        """
        # If no expected count provided, no validation needed
        if expected_count is None:
            return None

        # If counts match exactly, no alert
        if detected_count == expected_count:
            return None

        # Calculate variance
        variance = detected_count - expected_count
        variance_percentage = (variance / expected_count) * 100.0 if expected_count > 0 else 0.0

        logger.debug(
            f"Quantity validation: detected={detected_count}, expected={expected_count}, "
            f"variance={variance} ({variance_percentage:.1f}%)"
        )

        # Check if variance exceeds thresholds
        alert = None

        if variance < 0:  # Underage
            if abs(variance_percentage) >= self.config.underage_threshold_pct:
                alert = self._create_underage_alert(
                    detected_count, expected_count, variance_percentage, unit
                )
        else:  # Overage
            if variance_percentage >= self.config.overage_threshold_pct:
                alert = self._create_overage_alert(
                    detected_count, expected_count, variance_percentage, unit
                )

        if alert:
            logger.info(f"Quantity alert generated: {alert.type.value} - {alert.message}")

        return alert

    def _create_underage_alert(
        self,
        detected_count: int,
        expected_count: int,
        variance_percentage: float,
        unit: str,
    ) -> QuantityAlert:
        """Create underage alert"""
        return QuantityAlert(
            type=AlertType.UNDERAGE,
            message=f"Expected {expected_count} {unit} but detected {detected_count} {unit}",
            variance_percentage=variance_percentage,
        )

    def _create_overage_alert(
        self,
        detected_count: int,
        expected_count: int,
        variance_percentage: float,
        unit: str,
    ) -> QuantityAlert:
        """Create overage alert"""
        return QuantityAlert(
            type=AlertType.OVERAGE,
            message=f"Expected {expected_count} {unit} but detected {detected_count} {unit}",
            variance_percentage=variance_percentage,
        )

    def validate_batch(
        self,
        detections: list[tuple[int, Optional[int], str]],
    ) -> list[Optional[QuantityAlert]]:
        """
        Validate multiple quantities in batch.

        Args:
            detections: List of (detected_count, expected_count, unit) tuples

        Returns:
            List of QuantityAlert objects (None if no alert)
        """
        alerts = []

        for detected_count, expected_count, unit in detections:
            alert = self.validate_quantity(detected_count, expected_count, unit)
            alerts.append(alert)

        return alerts

    def calculate_variance_percentage(
        self, detected_count: int, expected_count: int
    ) -> float:
        """
        Calculate variance percentage.

        Args:
            detected_count: Detected quantity
            expected_count: Expected quantity

        Returns:
            Variance percentage (positive for overage, negative for underage)
        """
        if expected_count == 0:
            return 0.0

        variance = detected_count - expected_count
        variance_percentage = (variance / expected_count) * 100.0

        return variance_percentage

    def is_within_tolerance(
        self, detected_count: int, expected_count: int
    ) -> bool:
        """
        Check if detected count is within tolerance of expected count.

        Args:
            detected_count: Detected quantity
            expected_count: Expected quantity

        Returns:
            True if within tolerance, False otherwise
        """
        variance_pct = abs(self.calculate_variance_percentage(detected_count, expected_count))

        # Use the more lenient threshold
        threshold = max(
            self.config.underage_threshold_pct, self.config.overage_threshold_pct
        )

        return variance_pct < threshold
