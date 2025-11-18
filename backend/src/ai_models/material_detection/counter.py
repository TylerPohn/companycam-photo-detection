"""Density estimation CNN for accurate material unit counting (Mock Implementation)"""

import logging
import random
import time
from typing import List, Tuple, Dict, Optional
from PIL import Image
import numpy as np

from .config import CounterConfig
from .detector import DetectionResult
from src.schemas.material_detection import MaterialType, BoundingBox

logger = logging.getLogger(__name__)


class CountResult:
    """Result from density estimation counting"""

    def __init__(
        self,
        material_type: MaterialType,
        count: int,
        confidence: float,
        refined_boxes: List[BoundingBox],
    ):
        self.material_type = material_type
        self.count = count
        self.confidence = confidence
        self.refined_boxes = refined_boxes


class MaterialCounter:
    """
    Density estimation CNN for accurate material unit counting.

    This is a MOCK implementation that simulates density estimation behavior.
    In production, this would load actual trained density estimation model.
    """

    def __init__(self, config: Optional[CounterConfig] = None):
        self.config = config or CounterConfig()
        self.model_loaded = False
        self.inference_count = 0
        logger.info(f"Initializing MaterialCounter with config: {self.config.model_dump()}")

    def load_model(self):
        """
        Load density estimation CNN model from weights.

        In production, this would load a trained density estimation model.
        """
        logger.info(f"Loading density estimation model from {self.config.model_path}")
        # Simulate model loading time
        time.sleep(0.01)
        self.model_loaded = True
        logger.info("Density estimation model loaded successfully (MOCK)")

    def count_materials(
        self,
        image: Image.Image,
        detections: List[DetectionResult],
    ) -> Dict[MaterialType, CountResult]:
        """
        Count material units using density estimation.

        Args:
            image: PIL Image
            detections: Initial detections from YOLOv8

        Returns:
            Dictionary mapping MaterialType to CountResult
        """
        if not self.model_loaded:
            self.load_model()

        start_time = time.time()

        # Group detections by material type
        detections_by_type = self._group_by_type(detections)

        count_results = {}

        for material_type, type_detections in detections_by_type.items():
            # Refine count using density estimation
            count_result = self._estimate_density_count(
                image, material_type, type_detections
            )
            count_results[material_type] = count_result

        inference_time = (time.time() - start_time) * 1000
        self.inference_count += 1

        logger.debug(
            f"Density counting completed for {len(count_results)} material types "
            f"in {inference_time:.2f}ms"
        )

        return count_results

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

    def _estimate_density_count(
        self,
        image: Image.Image,
        material_type: MaterialType,
        detections: List[DetectionResult],
    ) -> CountResult:
        """
        Estimate accurate count using density estimation CNN.

        In production, this would:
        1. Extract regions around detections
        2. Run density estimation CNN to generate density map
        3. Count peaks in density map
        4. Merge nearby detections to avoid double-counting

        This is a MOCK implementation.
        """
        if not detections:
            return CountResult(
                material_type=material_type,
                count=0,
                confidence=0.0,
                refined_boxes=[],
            )

        # MOCK: Simulate density estimation refinement
        # In reality, this would run the CNN and refine counts

        # Merge nearby detections to avoid double-counting
        merged_boxes = self._merge_nearby_boxes(detections)

        # Count is the number of unique regions detected
        count = len(merged_boxes)

        # Calculate average confidence
        if detections:
            avg_confidence = sum(d.confidence for d in detections) / len(detections)
        else:
            avg_confidence = 0.0

        # MOCK: Simulate slight adjustment from density estimation
        # Sometimes density estimation finds a few more/fewer units
        adjustment = random.choice([-1, 0, 0, 1])
        count = max(1, count + adjustment)

        logger.debug(
            f"Density estimation: {material_type.value} - "
            f"Initial detections: {len(detections)}, "
            f"Merged boxes: {len(merged_boxes)}, "
            f"Final count: {count}"
        )

        return CountResult(
            material_type=material_type,
            count=count,
            confidence=avg_confidence,
            refined_boxes=merged_boxes,
        )

    def _merge_nearby_boxes(
        self, detections: List[DetectionResult]
    ) -> List[BoundingBox]:
        """
        Merge nearby bounding boxes to avoid double-counting.

        Uses IoU (Intersection over Union) to determine if boxes overlap.
        """
        if not detections:
            return []

        # Sort by confidence
        sorted_detections = sorted(detections, key=lambda d: d.confidence, reverse=True)

        merged_boxes = []
        used = set()

        for i, detection in enumerate(sorted_detections):
            if i in used:
                continue

            # Start with current box
            current_box = detection.bounding_box

            # Check if it overlaps with any subsequent boxes
            for j in range(i + 1, len(sorted_detections)):
                if j in used:
                    continue

                other_box = sorted_detections[j].bounding_box

                # Calculate distance between box centers
                center1_x = current_box.x + current_box.width / 2
                center1_y = current_box.y + current_box.height / 2
                center2_x = other_box.x + other_box.width / 2
                center2_y = other_box.y + other_box.height / 2

                distance = np.sqrt(
                    (center1_x - center2_x) ** 2 + (center1_y - center2_y) ** 2
                )

                # Merge if boxes are very close
                if distance < self.config.merge_distance_threshold:
                    used.add(j)

            merged_boxes.append(current_box)
            used.add(i)

        return merged_boxes

    def _calculate_iou(self, box1: BoundingBox, box2: BoundingBox) -> float:
        """
        Calculate Intersection over Union (IoU) between two bounding boxes.
        """
        # Calculate intersection
        x_left = max(box1.x, box2.x)
        y_top = max(box1.y, box2.y)
        x_right = min(box1.x + box1.width, box2.x + box2.width)
        y_bottom = min(box1.y + box1.height, box2.y + box2.height)

        if x_right < x_left or y_bottom < y_top:
            return 0.0

        intersection_area = (x_right - x_left) * (y_bottom - y_top)

        # Calculate union
        box1_area = box1.width * box1.height
        box2_area = box2.width * box2.height
        union_area = box1_area + box2_area - intersection_area

        if union_area == 0:
            return 0.0

        return intersection_area / union_area

    def get_inference_stats(self) -> dict:
        """Get inference statistics"""
        return {
            "model_loaded": self.model_loaded,
            "inference_count": self.inference_count,
            "config": self.config.model_dump(),
        }
