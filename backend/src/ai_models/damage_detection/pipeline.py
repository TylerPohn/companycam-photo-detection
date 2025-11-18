"""End-to-end damage detection pipeline orchestrating all models"""

import logging
import time
from typing import List, Optional, Dict
from PIL import Image
import io

from .config import DamageDetectionConfig
from .detector import DamageDetector, DetectionResult
from .segmenter import DamageSegmenter
from .severity_classifier import SeverityClassifier
from src.schemas.damage_detection import (
    DamageDetection,
    DamageDetectionResponse,
    DamageSummary,
    DamageType,
)

logger = logging.getLogger(__name__)


class DamageDetectionPipeline:
    """
    End-to-end pipeline for damage detection combining:
    - YOLOv8 object detection
    - U-Net semantic segmentation
    - ResNet50 severity classification
    """

    def __init__(self, config: Optional[DamageDetectionConfig] = None):
        self.config = config or DamageDetectionConfig()
        self.detector = DamageDetector(self.config.detector)
        self.segmenter = DamageSegmenter(self.config.segmenter)
        self.severity_classifier = SeverityClassifier(self.config.severity_classifier)
        self.pipeline_loaded = False
        logger.info("Initializing DamageDetectionPipeline")

    def load_models(self):
        """Load all models for inference"""
        logger.info("Loading all damage detection models...")
        start_time = time.time()

        self.detector.load_model()
        if self.config.enable_segmentation:
            self.segmenter.load_model()
        if self.config.enable_severity:
            self.severity_classifier.load_model()

        load_time = (time.time() - start_time) * 1000
        self.pipeline_loaded = True

        logger.info(f"All models loaded in {load_time:.2f}ms")

    def process_image(
        self,
        image: Image.Image,
        s3_service=None,
        photo_id: Optional[str] = None,
    ) -> DamageDetectionResponse:
        """
        Process a single image through the full damage detection pipeline.

        Args:
            image: PIL Image to process
            s3_service: Optional S3 service for uploading segmentation masks
            photo_id: Optional photo ID for S3 key generation

        Returns:
            DamageDetectionResponse with all detections and metadata
        """
        if not self.pipeline_loaded:
            self.load_models()

        start_time = time.time()

        logger.info(f"Processing image through damage detection pipeline (size: {image.size})")

        # Step 1: Run object detection (YOLOv8)
        detection_results = self.detector.detect(image)
        logger.debug(f"YOLOv8 detected {len(detection_results)} damage regions")

        # Step 2 & 3: For each detection, run segmentation and severity classification
        damage_detections = []

        for idx, detection in enumerate(detection_results):
            # Generate segmentation mask
            segmentation_mask_url = None
            area_percentage = 0.0

            if self.config.enable_segmentation:
                try:
                    mask, area_pct = self.segmenter.segment(
                        image, detection.bounding_box
                    )
                    area_percentage = area_pct

                    # Upload mask to S3 if service provided
                    if s3_service and photo_id:
                        mask_bytes = self.segmenter.mask_to_bytes(mask)
                        mask_key = (
                            f"{self.config.s3_prefix}{photo_id}_damage{idx}.png"
                        )
                        segmentation_mask_url = s3_service.upload_bytes(
                            mask_bytes, mask_key, content_type="image/png"
                        )
                        logger.debug(f"Uploaded segmentation mask to {segmentation_mask_url}")

                except Exception as e:
                    logger.error(f"Segmentation failed for detection {idx}: {e}")

            # Classify severity
            severity = None
            severity_confidence = detection.confidence

            if self.config.enable_severity:
                try:
                    severity, severity_confidence = (
                        self.severity_classifier.classify_severity(
                            image,
                            detection.bounding_box,
                            detection.damage_type,
                            detection.confidence,
                        )
                    )
                except Exception as e:
                    logger.error(f"Severity classification failed for detection {idx}: {e}")
                    # Default to moderate severity
                    from src.schemas.damage_detection import DamageSeverity
                    severity = DamageSeverity.MODERATE

            # Create damage detection object
            damage_det = DamageDetection(
                type=detection.damage_type,
                confidence=detection.confidence,
                severity=severity,
                bounding_box=detection.bounding_box,
                segmentation_mask=segmentation_mask_url,
                area_percentage=area_percentage,
            )

            damage_detections.append(damage_det)

        # Step 4: Generate summary and tags
        summary = self._generate_summary(damage_detections, image.size)
        tags = self._generate_tags(damage_detections)

        # Calculate overall confidence (average of detection confidences)
        overall_confidence = 0.0
        if damage_detections:
            overall_confidence = sum(d.confidence for d in damage_detections) / len(
                damage_detections
            )

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Create response
        response = DamageDetectionResponse(
            detections=damage_detections,
            tags=tags,
            summary=summary,
            processing_time_ms=processing_time_ms,
            model_version=self.config.model_version,
            confidence=overall_confidence,
        )

        logger.info(
            f"Damage detection completed: {len(damage_detections)} detections "
            f"in {processing_time_ms}ms"
        )

        return response

    def _generate_summary(
        self, detections: List[DamageDetection], image_size: tuple
    ) -> DamageSummary:
        """
        Generate summary statistics from detections.

        Args:
            detections: List of damage detections
            image_size: (width, height) of original image

        Returns:
            DamageSummary object
        """
        # Calculate total damage area
        total_area_pct = sum(d.area_percentage for d in detections)

        # Count damage types
        damage_type_dist = {}
        for damage_type in DamageType:
            count = sum(1 for d in detections if d.type == damage_type)
            damage_type_dist[damage_type.value] = count

        return DamageSummary(
            total_damage_area_percentage=min(100.0, total_area_pct),
            damage_type_distribution=damage_type_dist,
        )

    def _generate_tags(self, detections: List[DamageDetection]) -> List[str]:
        """
        Generate descriptive tags based on detections.

        Args:
            detections: List of damage detections

        Returns:
            List of tags
        """
        tags = []

        if not detections:
            tags.append("no_damage_detected")
            return tags

        # Add base tag
        tags.append("roof_damage")

        # Add damage type tags
        damage_types = set(d.type for d in detections)
        for damage_type in damage_types:
            if damage_type == DamageType.HAIL_DAMAGE:
                tags.append("hail_impact")
            elif damage_type == DamageType.WIND_DAMAGE:
                tags.append("wind_damage")
            elif damage_type == DamageType.MISSING_SHINGLES:
                tags.append("missing_shingles")

        # Add severity tags
        severities = set(d.severity for d in detections)
        if any(s.value == "severe" for s in severities):
            tags.append("severe_damage")
            tags.append("urgent")

        # Check if insurance claim worthy (moderate or severe damage)
        if any(d.severity.value in ["moderate", "severe"] for d in detections):
            tags.append("insurance_claim")

        # Add count-based tags
        if len(detections) >= 5:
            tags.append("multiple_damages")

        return tags

    def process_batch(
        self,
        images: List[Image.Image],
        s3_service=None,
        photo_ids: Optional[List[str]] = None,
    ) -> Dict[str, DamageDetectionResponse]:
        """
        Process multiple images in batch.

        Args:
            images: List of PIL Images to process
            s3_service: Optional S3 service for uploading masks
            photo_ids: Optional list of photo IDs

        Returns:
            Dictionary mapping index/photo_id to DamageDetectionResponse
        """
        if not self.pipeline_loaded:
            self.load_models()

        logger.info(f"Processing batch of {len(images)} images")
        start_time = time.time()

        results = {}

        for idx, image in enumerate(images):
            photo_id = photo_ids[idx] if photo_ids and idx < len(photo_ids) else str(idx)
            try:
                response = self.process_image(image, s3_service, photo_id)
                results[photo_id] = response
            except Exception as e:
                logger.error(f"Failed to process image {photo_id}: {e}")
                # Return error response
                results[photo_id] = None

        batch_time = (time.time() - start_time) * 1000
        logger.info(f"Batch processing completed in {batch_time:.2f}ms")

        return results

    def get_stats(self) -> dict:
        """Get pipeline statistics"""
        return {
            "pipeline_loaded": self.pipeline_loaded,
            "model_version": self.config.model_version,
            "detector_stats": self.detector.get_inference_stats(),
            "segmenter_stats": self.segmenter.get_inference_stats(),
            "severity_classifier_stats": self.severity_classifier.get_inference_stats(),
        }
