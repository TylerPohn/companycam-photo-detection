"""End-to-end Volume Estimation Pipeline"""

import logging
import time
from typing import Dict, Optional, Tuple
import numpy as np
from PIL import Image
import io

from .config import VolumeEstimationConfig
from .depth_estimator import DepthEstimator
from .material_segmenter import MaterialSegmenter
from .scale_detector import ScaleDetector
from .volume_calculator import VolumeCalculator

logger = logging.getLogger(__name__)


class VolumeEstimationPipeline:
    """
    End-to-end pipeline for volume estimation.
    Orchestrates depth estimation, material segmentation, scale detection, and volume calculation.
    """

    def __init__(self, config: Optional[VolumeEstimationConfig] = None):
        """
        Initialize volume estimation pipeline.

        Args:
            config: VolumeEstimationConfig instance (uses default if None)
        """
        from .config import default_config

        self.config = config or default_config
        self.device = self.config.get_device()

        # Initialize components
        self.depth_estimator = DepthEstimator(self.config.depth_estimation)
        self.material_segmenter = MaterialSegmenter(self.config.material_segmentation)
        self.scale_detector = ScaleDetector(self.config.scale_detection)
        self.volume_calculator = VolumeCalculator(self.config.volume_calculation)

        self._models_loaded = False
        self._inference_count = 0
        self._total_processing_time = 0.0

        logger.info(f"VolumeEstimationPipeline initialized (device={self.device})")

    def load_models(self):
        """Load all models in the pipeline"""
        if self._models_loaded:
            logger.debug("Models already loaded")
            return

        logger.info("Loading all models in volume estimation pipeline...")

        start_time = time.time()

        # Load all models
        self.depth_estimator.load_model()
        self.material_segmenter.load_model()
        self.scale_detector.load_model()

        load_time = time.time() - start_time
        self._models_loaded = True

        logger.info(f"All models loaded successfully in {load_time:.2f}s")

    def estimate_volume(
        self,
        image: np.ndarray,
        save_depth_map: bool = True
    ) -> Dict:
        """
        Run complete volume estimation pipeline.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format
            save_depth_map: Whether to generate depth map visualization

        Returns:
            Dict with volume estimation results matching response schema
        """
        if not self._models_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")

        pipeline_start_time = time.time()

        try:
            # Step 1: Depth Estimation
            logger.debug("Step 1/4: Estimating depth...")
            depth_start = time.time()
            depth_map, depth_metadata = self.depth_estimator.estimate_depth(image)
            depth_time = (time.time() - depth_start) * 1000

            # Step 2: Material Segmentation
            logger.debug("Step 2/4: Segmenting material...")
            seg_start = time.time()
            material_mask, material_type, seg_metadata = self.material_segmenter.segment(image)
            seg_time = (time.time() - seg_start) * 1000

            # Step 3: Scale Reference Detection
            logger.debug("Step 3/4: Detecting scale reference...")
            scale_start = time.time()
            scale_reference, scale_metadata = self.scale_detector.detect_scale_reference(
                image, depth_map
            )
            scale_time = (time.time() - scale_start) * 1000

            # Step 4: Volume Calculation
            logger.debug("Step 4/4: Calculating volume...")
            vol_start = time.time()
            volume, volume_metadata = self.volume_calculator.calculate_volume(
                depth_map, material_mask, scale_reference, material_type
            )
            vol_time = (time.time() - vol_start) * 1000

            # Calculate total processing time
            total_time = (time.time() - pipeline_start_time) * 1000

            # Update stats
            self._inference_count += 1
            self._total_processing_time += total_time

            # Calculate confidence scores
            confidence_breakdown = self._calculate_confidence_breakdown(
                depth_metadata, seg_metadata, scale_metadata, volume_metadata
            )
            overall_confidence = self._calculate_overall_confidence(confidence_breakdown)

            # Determine if user confirmation is needed
            requires_confirmation = overall_confidence < self.config.confidence.low_confidence_threshold

            # Calculate volume range
            volume_range = self.volume_calculator.calculate_volume_range(
                volume, overall_confidence, scale_reference
            )

            # Generate depth map visualization if requested
            depth_map_url = None
            if save_depth_map:
                depth_map_url = self._generate_depth_map_placeholder()

            # Build response
            result = {
                "material": material_type,
                "estimated_volume": round(volume, 2),
                "unit": self.config.volume_calculation.default_unit,
                "confidence": round(overall_confidence, 3),
                "requires_confirmation": requires_confirmation,
                "volume_range": volume_range,
                "depth_map": depth_map_url,
                "scale_reference": self._format_scale_reference(scale_reference),
                "calculation_method": volume_metadata.get("method", "unknown"),
                "processing_time_ms": round(total_time, 2),
                "model_version": self.config.model_version,
                "confidence_breakdown": confidence_breakdown,
                "component_timings_ms": {
                    "depth_estimation": round(depth_time, 2),
                    "material_segmentation": round(seg_time, 2),
                    "scale_detection": round(scale_time, 2),
                    "volume_calculation": round(vol_time, 2)
                }
            }

            logger.info(
                f"Volume estimation complete: {volume:.2f} {self.config.volume_calculation.default_unit} "
                f"({material_type}, confidence={overall_confidence:.2f}, time={total_time:.0f}ms)"
            )

            return result

        except Exception as e:
            logger.error(f"Volume estimation pipeline failed: {e}")
            raise

    def _calculate_confidence_breakdown(
        self,
        depth_metadata: Dict,
        seg_metadata: Dict,
        scale_metadata: Dict,
        volume_metadata: Dict
    ) -> Dict[str, float]:
        """
        Calculate confidence scores for each pipeline component.

        Returns:
            Dict with component confidence scores
        """
        # Depth estimation confidence
        depth_confidence = depth_metadata.get("confidence", 0.8)

        # Material segmentation confidence
        seg_confidence = seg_metadata.get("material_confidence", 0.8)

        # Scale detection confidence
        if scale_metadata.get("has_scale_reference"):
            # Use confidence from best reference
            scale_confidence = 0.85
        else:
            # No reference found - lower confidence
            scale_confidence = 0.5

        return {
            "depth_estimation": round(depth_confidence, 3),
            "material_detection": round(seg_confidence, 3),
            "scale_detection": round(scale_confidence, 3)
        }

    def _calculate_overall_confidence(self, confidence_breakdown: Dict[str, float]) -> float:
        """
        Calculate overall confidence as weighted average.

        Args:
            confidence_breakdown: Component confidences

        Returns:
            Overall confidence score
        """
        weights = {
            "depth_estimation": self.config.confidence.depth_weight,
            "material_detection": self.config.confidence.segmentation_weight,
            "scale_detection": self.config.confidence.scale_weight
        }

        overall = 0.0
        for component, score in confidence_breakdown.items():
            weight = weights.get(component, 0.33)
            overall += score * weight

        return min(max(overall, 0.0), 1.0)

    def _format_scale_reference(self, scale_reference: Optional[Dict]) -> Optional[Dict]:
        """
        Format scale reference for response.

        Args:
            scale_reference: Raw scale reference or None

        Returns:
            Formatted scale reference or None
        """
        if scale_reference is None:
            return None

        return {
            "type": scale_reference.get("type", "unknown"),
            "confidence": scale_reference.get("confidence", 0.0),
            "estimated_height_cm": scale_reference.get("estimated_height_cm"),
            "estimated_diameter_cm": scale_reference.get("estimated_diameter_cm")
        }

    def _generate_depth_map_placeholder(self) -> str:
        """
        Generate placeholder URL for depth map.
        In production, this would save the depth map to S3.

        Returns:
            Depth map URL
        """
        # Placeholder - in production this would:
        # 1. Generate depth map visualization
        # 2. Upload to S3
        # 3. Return S3 URL
        bucket = self.config.s3_bucket
        prefix = self.config.s3_depth_map_prefix
        photo_id = f"photo_{self._inference_count}"

        return f"s3://{bucket}/{prefix}{photo_id}.png"

    def estimate_volume_from_file(self, image_path: str) -> Dict:
        """
        Estimate volume from image file path.

        Args:
            image_path: Path to image file

        Returns:
            Volume estimation result
        """
        # Load image
        image = Image.open(image_path)
        image_array = np.array(image.convert("RGB"))

        return self.estimate_volume(image_array)

    def estimate_volume_from_bytes(self, image_bytes: bytes) -> Dict:
        """
        Estimate volume from image bytes.

        Args:
            image_bytes: Image data as bytes

        Returns:
            Volume estimation result
        """
        # Load image from bytes
        image = Image.open(io.BytesIO(image_bytes))
        image_array = np.array(image.convert("RGB"))

        return self.estimate_volume(image_array)

    def get_stats(self) -> Dict:
        """
        Get pipeline statistics.

        Returns:
            Dict with pipeline stats
        """
        avg_time = self._total_processing_time / max(self._inference_count, 1)

        return {
            "inference_count": self._inference_count,
            "total_processing_time_ms": round(self._total_processing_time, 2),
            "average_processing_time_ms": round(avg_time, 2),
            "models_loaded": self._models_loaded,
            "model_version": self.config.model_version,
            "device": self.device,
            "components": {
                "depth_estimator": self.depth_estimator.get_stats() if self._models_loaded else {},
                "material_segmenter": self.material_segmenter.get_stats() if self._models_loaded else {},
                "scale_detector": self.scale_detector.get_stats() if self._models_loaded else {}
            }
        }

    def unload_models(self):
        """Unload models to free memory"""
        # In a real implementation, this would explicitly free GPU memory
        self._models_loaded = False
        logger.info("Models marked for unloading")
