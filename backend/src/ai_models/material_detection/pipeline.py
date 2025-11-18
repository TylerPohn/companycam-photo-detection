"""End-to-end material detection pipeline orchestrating all models"""

import logging
import time
from typing import List, Optional, Dict
from PIL import Image

from .config import MaterialDetectionConfig
from .detector import MaterialDetector, DetectionResult
from .counter import MaterialCounter
from .brand_detector import BrandDetector
from .material_validator import MaterialValidator
from .material_database import MaterialDatabase, get_material_database
from src.schemas.material_detection import (
    MaterialDetection,
    MaterialDetectionResponse,
    MaterialSummary,
    MaterialType,
    BoundingBox,
)

logger = logging.getLogger(__name__)


class MaterialDetectionPipeline:
    """
    End-to-end pipeline for material detection combining:
    - YOLOv8 object detection
    - Density estimation counting
    - OCR brand detection
    - Quantity validation
    """

    def __init__(
        self,
        config: Optional[MaterialDetectionConfig] = None,
        material_db: Optional[MaterialDatabase] = None,
    ):
        self.config = config or MaterialDetectionConfig()
        self.material_db = material_db or get_material_database(
            self.config.materials_db_path, self.config.brands_db_path
        )
        self.detector = MaterialDetector(self.config.detector)
        self.counter = MaterialCounter(self.config.counter)
        self.brand_detector = BrandDetector(self.config.brand_detector, self.material_db)
        self.validator = MaterialValidator(self.config.validator)
        self.pipeline_loaded = False
        logger.info("Initializing MaterialDetectionPipeline")

    def load_models(self):
        """Load all models for inference"""
        logger.info("Loading all material detection models...")
        start_time = time.time()

        self.detector.load_model()
        if self.config.enable_counting:
            self.counter.load_model()
        if self.config.enable_brand_detection:
            self.brand_detector.initialize_ocr()

        # Load material database
        if not self.material_db._loaded:
            self.material_db.load()

        load_time = (time.time() - start_time) * 1000
        self.pipeline_loaded = True

        logger.info(f"All models loaded in {load_time:.2f}ms")

    def process_image(
        self,
        image: Image.Image,
        expected_materials: Optional[Dict[str, int]] = None,
    ) -> MaterialDetectionResponse:
        """
        Process a single image through the full material detection pipeline.

        Args:
            image: PIL Image to process
            expected_materials: Optional dict mapping material_type -> expected_quantity

        Returns:
            MaterialDetectionResponse with all detections and metadata
        """
        if not self.pipeline_loaded:
            self.load_models()

        start_time = time.time()

        logger.info(f"Processing image through material detection pipeline (size: {image.size})")

        # Step 1: Run object detection (YOLOv8)
        detection_results = self.detector.detect(image)
        logger.debug(f"YOLOv8 detected {len(detection_results)} material units")

        # Step 2: Count materials using density estimation
        count_results = {}
        if self.config.enable_counting and detection_results:
            count_results = self.counter.count_materials(image, detection_results)
            logger.debug(f"Density counting completed for {len(count_results)} material types")

        # Step 3: For each material type, detect brand and validate quantity
        material_detections = []

        # Group detections by material type
        detections_by_type = self._group_by_type(detection_results)

        for material_type, type_detections in detections_by_type.items():
            # Get count result
            if material_type in count_results:
                count_result = count_results[material_type]
                count = count_result.count
                confidence = count_result.confidence
                bounding_boxes = [
                    bbox for bbox in count_result.refined_boxes
                ]
            else:
                # Fallback: use raw detection count
                count = len(type_detections)
                confidence = sum(d.confidence for d in type_detections) / len(type_detections)
                bounding_boxes = [d.bounding_box for d in type_detections]

            # Detect brand
            brand_name = None
            if self.config.enable_brand_detection and bounding_boxes:
                try:
                    # Use first bounding box for brand detection
                    brand_result = self.brand_detector.detect_brand(
                        image, material_type, bounding_boxes[0]
                    )
                    if brand_result.confidence >= self.config.brand_detector.confidence_threshold:
                        brand_name = brand_result.brand_name
                except Exception as e:
                    logger.error(f"Brand detection failed for {material_type.value}: {e}")

            # Get material unit
            unit = self.material_db.get_material_unit(material_type.value)

            # Validate quantity
            expected_quantity = None
            alert = None
            if expected_materials and material_type.value in expected_materials:
                expected_quantity = expected_materials[material_type.value]
                alert = self.validator.validate_quantity(
                    count, expected_quantity, unit.value
                )

            # Create material detection object
            material_det = MaterialDetection(
                type=material_type,
                brand=brand_name,
                count=count,
                confidence=confidence,
                unit=unit,
                expected_quantity=expected_quantity,
                alert=alert,
                bounding_boxes=bounding_boxes[:10],  # Limit to 10 boxes for response size
            )

            material_detections.append(material_det)

        # Step 4: Generate summary and tags
        summary = self._generate_summary(material_detections)
        tags = self._generate_tags(material_detections)

        # Calculate overall confidence (average of material confidences)
        overall_confidence = 0.0
        if material_detections:
            overall_confidence = sum(m.confidence for m in material_detections) / len(
                material_detections
            )

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Create response
        response = MaterialDetectionResponse(
            materials=material_detections,
            tags=tags,
            summary=summary,
            processing_time_ms=processing_time_ms,
            model_version=self.config.model_version,
            confidence=overall_confidence,
        )

        logger.info(
            f"Material detection completed: {len(material_detections)} material types, "
            f"{summary.total_units} total units in {processing_time_ms}ms"
        )

        return response

    def _group_by_type(
        self, detections: List[DetectionResult]
    ) -> Dict[MaterialType, List[DetectionResult]]:
        """Group detections by material type"""
        grouped = {}
        for detection in detections:
            if detection.material_type not in grouped:
                grouped[detection.material_type] = []
            grouped[detection.material_type].append(detection)
        return grouped

    def _generate_summary(
        self, detections: List[MaterialDetection]
    ) -> MaterialSummary:
        """
        Generate summary statistics from detections.

        Args:
            detections: List of material detections

        Returns:
            MaterialSummary object
        """
        # Count total units
        total_units = sum(d.count for d in detections)

        # Count discrepancy alerts
        discrepancy_alerts = sum(1 for d in detections if d.alert is not None)

        return MaterialSummary(
            total_materials_detected=len(detections),
            total_units=total_units,
            discrepancy_alerts=discrepancy_alerts,
        )

    def _generate_tags(self, detections: List[MaterialDetection]) -> List[str]:
        """
        Generate descriptive tags based on detections.

        Args:
            detections: List of material detections

        Returns:
            List of tags
        """
        tags = []

        if not detections:
            tags.append("no_materials_detected")
            return tags

        # Add base tag
        tags.append("delivery_confirmation")

        # Add material type tags
        material_types = set(d.type for d in detections)
        for material_type in material_types:
            tags.append(material_type.value)

        # Add brand tags
        brands = set(d.brand for d in detections if d.brand)
        for brand in brands:
            # Normalize brand name for tag
            brand_tag = brand.lower().replace(" ", "_")
            tags.append(f"brand_{brand_tag}")

        # Add alert tags
        if any(d.alert is not None for d in detections):
            tags.append("quantity_discrepancy")

        if any(d.alert and d.alert.type.value == "underage" for d in detections):
            tags.append("underage_alert")

        if any(d.alert and d.alert.type.value == "overage" for d in detections):
            tags.append("overage_alert")

        # Add count-based tags
        total_units = sum(d.count for d in detections)
        if total_units >= 50:
            tags.append("large_delivery")
        elif total_units >= 20:
            tags.append("medium_delivery")
        else:
            tags.append("small_delivery")

        return tags

    def process_batch(
        self,
        images: List[Image.Image],
        expected_materials_list: Optional[List[Dict[str, int]]] = None,
    ) -> Dict[str, MaterialDetectionResponse]:
        """
        Process multiple images in batch.

        Args:
            images: List of PIL Images to process
            expected_materials_list: Optional list of expected materials dicts

        Returns:
            Dictionary mapping index to MaterialDetectionResponse
        """
        if not self.pipeline_loaded:
            self.load_models()

        logger.info(f"Processing batch of {len(images)} images")
        start_time = time.time()

        results = {}

        for idx, image in enumerate(images):
            expected_materials = None
            if expected_materials_list and idx < len(expected_materials_list):
                expected_materials = expected_materials_list[idx]

            try:
                response = self.process_image(image, expected_materials)
                results[str(idx)] = response
            except Exception as e:
                logger.error(f"Failed to process image {idx}: {e}")
                # Return None for failed images
                results[str(idx)] = None

        batch_time = (time.time() - start_time) * 1000
        logger.info(f"Batch processing completed in {batch_time:.2f}ms")

        return results

    def get_stats(self) -> dict:
        """Get pipeline statistics"""
        return {
            "pipeline_loaded": self.pipeline_loaded,
            "model_version": self.config.model_version,
            "detector_stats": self.detector.get_inference_stats(),
            "counter_stats": self.counter.get_inference_stats(),
            "brand_detector_stats": self.brand_detector.get_inference_stats(),
            "material_db_stats": self.material_db.get_stats(),
        }
