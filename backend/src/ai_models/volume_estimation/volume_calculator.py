"""Volume calculation using depth maps and scale references"""

import logging
from typing import Optional, Dict, Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class VolumeCalculator:
    """
    Calculate volume of loose materials using depth maps and scale references.
    Converts pixel-based depth into real-world volume estimates.
    """

    def __init__(self, config):
        """
        Initialize volume calculator.

        Args:
            config: VolumeCalculationConfig instance
        """
        self.config = config
        logger.info("VolumeCalculator initialized")

    def calculate_volume(
        self,
        depth_map: np.ndarray,
        material_mask: np.ndarray,
        scale_reference: Optional[Dict],
        material_type: str
    ) -> Tuple[float, Dict]:
        """
        Calculate volume of material using depth map and scale.

        Args:
            depth_map: Normalized depth map [0, 1] (H, W)
            material_mask: Binary mask of material region (H, W)
            scale_reference: Scale reference dict (can be None for fallback)
            material_type: Type of material (gravel, mulch, sand)

        Returns:
            Tuple of (volume_cubic_yards, calculation_metadata)
        """
        try:
            # Validate inputs
            if depth_map.shape != material_mask.shape:
                raise ValueError("Depth map and material mask must have same shape")

            # Check if material region is large enough
            material_pixels = material_mask.sum()
            if material_pixels < self.config.pixel_area_threshold:
                logger.warning(
                    f"Material region too small: {material_pixels} pixels "
                    f"(threshold: {self.config.pixel_area_threshold})"
                )
                return 0.0, {
                    "error": "Material region too small",
                    "material_pixels": int(material_pixels),
                    "method": "failed"
                }

            # Extract material depth
            material_depth = self._extract_material_depth(depth_map, material_mask)

            # Convert to real-world scale
            if scale_reference:
                real_world_depth, scale_factor = self._apply_scale_reference(
                    material_depth, scale_reference, depth_map, material_mask
                )
                calculation_method = f"depth_map_{scale_reference['type']}"
            else:
                # Fallback: use heuristic scaling
                real_world_depth, scale_factor = self._apply_heuristic_scale(
                    material_depth, depth_map.shape
                )
                calculation_method = "depth_map_heuristic"

            # Calculate volume in cubic meters
            volume_m3 = self._integrate_volume(real_world_depth, material_mask, scale_factor)

            # Convert to target unit (cubic yards by default)
            volume_target_unit = self._convert_units(volume_m3, self.config.default_unit)

            # Prepare metadata
            metadata = {
                "method": calculation_method,
                "volume_cubic_meters": round(volume_m3, 4),
                "volume_cubic_yards": round(volume_target_unit, 4),
                "scale_factor_cm_per_pixel": round(scale_factor, 4) if scale_factor else None,
                "material_pixels": int(material_pixels),
                "mean_depth_normalized": round(float(material_depth.mean()), 4),
                "max_depth_normalized": round(float(material_depth.max()), 4),
                "has_scale_reference": scale_reference is not None
            }

            logger.debug(
                f"Volume calculated: {volume_target_unit:.2f} cubic yards "
                f"(method: {calculation_method})"
            )

            return volume_target_unit, metadata

        except Exception as e:
            logger.error(f"Volume calculation failed: {e}")
            raise

    def _extract_material_depth(
        self, depth_map: np.ndarray, material_mask: np.ndarray
    ) -> np.ndarray:
        """
        Extract and process depth values for material region.

        Args:
            depth_map: Normalized depth map
            material_mask: Binary material mask

        Returns:
            Processed material depth map
        """
        # Apply smoothing to depth map
        kernel_size = self.config.smoothing_kernel_size
        smoothed_depth = cv2.GaussianBlur(depth_map, (kernel_size, kernel_size), 0)

        # Extract material region
        material_depth = smoothed_depth.copy()
        material_depth[material_mask == 0] = 0

        # Estimate ground plane (lowest depth in material region)
        # This represents the base level for volume calculation
        material_depth_values = smoothed_depth[material_mask > 0]
        if len(material_depth_values) > 0:
            # Use 10th percentile as ground level to be robust to noise
            ground_level = np.percentile(material_depth_values, 10)

            # Subtract ground level to get height above base
            material_depth = np.maximum(smoothed_depth - ground_level, 0)
            material_depth[material_mask == 0] = 0

        return material_depth

    def _apply_scale_reference(
        self,
        material_depth: np.ndarray,
        scale_reference: Dict,
        depth_map: np.ndarray,
        material_mask: np.ndarray
    ) -> Tuple[np.ndarray, float]:
        """
        Apply scale reference to convert depth to real-world units.

        Args:
            material_depth: Extracted material depth
            scale_reference: Scale reference dict
            depth_map: Original depth map
            material_mask: Material mask

        Returns:
            Tuple of (real_world_depth_cm, scale_factor_cm_per_pixel)
        """
        # Get pixels per cm from scale reference
        pixels_per_cm = scale_reference.get("pixels_per_cm", 1.0)

        if pixels_per_cm <= 0:
            logger.warning("Invalid pixels_per_cm, using fallback")
            return self._apply_heuristic_scale(material_depth, depth_map.shape)

        # Calculate cm per pixel (inverse)
        cm_per_pixel = 1.0 / pixels_per_cm

        # Convert depth map from normalized to cm
        # Assume depth_map [0, 1] corresponds to [0, max_depth_meters] in real world
        max_depth_cm = self.config.depth_max_meters * 100

        # Scale material depth to cm
        real_world_depth = material_depth * max_depth_cm * cm_per_pixel

        return real_world_depth, cm_per_pixel

    def _apply_heuristic_scale(
        self, material_depth: np.ndarray, image_shape: Tuple
    ) -> Tuple[np.ndarray, float]:
        """
        Apply heuristic scaling when no reference is available.

        Args:
            material_depth: Extracted material depth
            image_shape: Image dimensions

        Returns:
            Tuple of (real_world_depth_cm, scale_factor_estimate)
        """
        # Heuristic: assume typical construction photo shows ~5m x 5m area
        # This is a rough estimate and will have lower confidence

        h, w = image_shape
        typical_scene_width_cm = 500  # 5 meters
        cm_per_pixel = typical_scene_width_cm / w

        # Scale depth
        max_depth_cm = self.config.depth_max_meters * 100
        real_world_depth = material_depth * max_depth_cm * (cm_per_pixel / 100)

        logger.debug(f"Using heuristic scale: {cm_per_pixel:.2f} cm/pixel")

        return real_world_depth, cm_per_pixel

    def _integrate_volume(
        self,
        real_world_depth: np.ndarray,
        material_mask: np.ndarray,
        scale_factor: float
    ) -> float:
        """
        Integrate depth over material area to calculate volume.

        Args:
            real_world_depth: Depth in cm
            material_mask: Material mask
            scale_factor: cm per pixel

        Returns:
            Volume in cubic meters
        """
        # Each pixel represents an area in real world
        pixel_area_cm2 = scale_factor ** 2

        # Sum depth × area for all material pixels
        # Volume = Σ (depth_i × area_i)
        total_volume_cm3 = (real_world_depth * material_mask).sum() * pixel_area_cm2

        # Convert cm³ to m³
        volume_m3 = total_volume_cm3 / 1_000_000

        return volume_m3

    def _convert_units(self, volume_m3: float, target_unit: str) -> float:
        """
        Convert volume from cubic meters to target unit.

        Args:
            volume_m3: Volume in cubic meters
            target_unit: Target unit (cubic_yards, cubic_feet, etc.)

        Returns:
            Volume in target unit
        """
        conversions = self.config.unit_conversions

        if target_unit not in conversions:
            logger.warning(f"Unknown unit {target_unit}, using cubic_meters")
            return volume_m3

        # Get conversion factor from m³ to target unit
        # The config stores factor to convert TO cubic meters, so we need inverse
        to_m3_factor = conversions[target_unit]

        if to_m3_factor == 0:
            return volume_m3

        # Convert: volume_target = volume_m3 / to_m3_factor
        volume_target = volume_m3 / to_m3_factor

        return volume_target

    def calculate_volume_range(
        self,
        volume: float,
        confidence: float,
        scale_reference: Optional[Dict]
    ) -> Dict[str, float]:
        """
        Calculate uncertainty range for volume estimate.

        Args:
            volume: Estimated volume
            confidence: Overall confidence score
            scale_reference: Scale reference (if available)

        Returns:
            Dict with min/max volume bounds
        """
        # Base uncertainty factor
        if scale_reference:
            # With reference: 10-20% uncertainty
            base_uncertainty = 0.15
        else:
            # Without reference: 25-40% uncertainty
            base_uncertainty = 0.35

        # Adjust based on confidence
        # Lower confidence → higher uncertainty
        uncertainty_factor = base_uncertainty * (2.0 - confidence)

        # Calculate range
        min_volume = volume * (1.0 - uncertainty_factor)
        max_volume = volume * (1.0 + uncertainty_factor)

        return {
            "min": round(max(0, min_volume), 2),
            "max": round(max_volume, 2)
        }

    def estimate_material_weight(
        self, volume_m3: float, material_type: str
    ) -> Optional[Dict[str, float]]:
        """
        Estimate material weight from volume (optional feature).

        Args:
            volume_m3: Volume in cubic meters
            material_type: Type of material

        Returns:
            Dict with weight estimates or None
        """
        # This would use material density data
        # Not implemented in MVP but included for future enhancement
        return None
