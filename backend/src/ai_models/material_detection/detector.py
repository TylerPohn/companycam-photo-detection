"""YOLOv8-based material detection model wrapper (Mock Implementation)"""

import logging
import random
import time
from typing import List, Tuple, Optional
from PIL import Image
import numpy as np

from .config import DetectorConfig
from src.schemas.material_detection import MaterialType, BoundingBox

logger = logging.getLogger(__name__)


class DetectionResult:
    """Single detection result from YOLOv8"""

    def __init__(
        self,
        material_type: MaterialType,
        confidence: float,
        bounding_box: BoundingBox,
    ):
        self.material_type = material_type
        self.confidence = confidence
        self.bounding_box = bounding_box


class MaterialDetector:
    """
    YOLOv8-based material detector for construction materials.

    This is a MOCK implementation that simulates YOLOv8 behavior.
    In production, this would load actual trained YOLOv8 weights.
    """

    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config or DetectorConfig()
        self.model_loaded = False
        self.inference_count = 0
        logger.info(f"Initializing MaterialDetector with config: {self.config.model_dump()}")

    def load_model(self):
        """
        Load YOLOv8 model from weights.

        In production, this would use:
        from ultralytics import YOLO
        self.model = YOLO(self.config.model_path)
        """
        logger.info(f"Loading YOLOv8 model from {self.config.model_path}")
        # Simulate model loading time
        time.sleep(0.01)
        self.model_loaded = True
        logger.info("YOLOv8 material detection model loaded successfully (MOCK)")

    def preprocess_image(self, image: Image.Image) -> Tuple[np.ndarray, Tuple[int, int]]:
        """
        Preprocess image for YOLOv8 inference.

        Args:
            image: PIL Image

        Returns:
            Preprocessed image array and original size
        """
        original_size = image.size

        # Resize to model input size while maintaining aspect ratio
        image = image.convert("RGB")
        image = image.resize((self.config.input_size, self.config.input_size), Image.LANCZOS)

        # Convert to numpy array and normalize
        image_array = np.array(image, dtype=np.float32) / 255.0

        return image_array, original_size

    def detect(self, image: Image.Image) -> List[DetectionResult]:
        """
        Run material detection on an image.

        Args:
            image: PIL Image to detect materials in

        Returns:
            List of DetectionResult objects

        Note:
            This is a MOCK implementation. In production, this would run actual YOLOv8 inference.
        """
        if not self.model_loaded:
            self.load_model()

        start_time = time.time()

        # Preprocess image
        processed_image, original_size = self.preprocess_image(image)
        img_width, img_height = original_size

        # MOCK: Generate realistic detections
        detections = self._generate_mock_detections(img_width, img_height)

        # Filter by confidence threshold
        filtered_detections = [
            d for d in detections if d.confidence >= self.config.confidence_threshold
        ]

        # Apply NMS (Non-Maximum Suppression) - simplified mock version
        final_detections = self._apply_nms(filtered_detections)

        # Limit max detections
        final_detections = final_detections[: self.config.max_detections]

        inference_time = (time.time() - start_time) * 1000
        self.inference_count += 1

        logger.debug(
            f"YOLOv8 material detection completed: {len(final_detections)} detections "
            f"in {inference_time:.2f}ms"
        )

        return final_detections

    def _generate_mock_detections(self, img_width: int, img_height: int) -> List[DetectionResult]:
        """
        Generate realistic mock detections for testing.

        In production, this would be replaced with actual YOLOv8 model inference.
        """
        detections = []

        # Randomly generate material detections (1-3 material types)
        num_material_types = random.randint(1, 3)

        material_types = [
            MaterialType.SHINGLES,
            MaterialType.PLYWOOD,
            MaterialType.DRYWALL,
            MaterialType.INSULATION,
        ]

        selected_types = random.sample(material_types, num_material_types)

        for material_type in selected_types:
            # Generate multiple units for each material type
            num_units = random.randint(3, 8)

            for _ in range(num_units):
                # Random confidence (biased toward higher values)
                confidence = random.uniform(0.70, 0.98)

                # Random bounding box for material unit
                box_width = random.randint(60, min(250, img_width // 3))
                box_height = random.randint(60, min(250, img_height // 3))
                x = random.randint(0, max(0, img_width - box_width))
                y = random.randint(0, max(0, img_height - box_height))

                bounding_box = BoundingBox(
                    x=x, y=y, width=box_width, height=box_height, confidence=confidence
                )

                detections.append(
                    DetectionResult(
                        material_type=material_type,
                        confidence=confidence,
                        bounding_box=bounding_box,
                    )
                )

        return detections

    def _apply_nms(self, detections: List[DetectionResult]) -> List[DetectionResult]:
        """
        Apply Non-Maximum Suppression to remove overlapping detections.

        This is a simplified mock version. In production, use proper NMS algorithm
        to calculate IoU and suppress overlapping boxes.
        """
        if len(detections) <= 1:
            return detections

        # Sort by confidence (descending)
        sorted_detections = sorted(detections, key=lambda d: d.confidence, reverse=True)

        # Keep top detections (simplified NMS)
        # In production, calculate IoU and suppress overlapping boxes
        return sorted_detections

    def get_inference_stats(self) -> dict:
        """Get inference statistics"""
        return {
            "model_loaded": self.model_loaded,
            "inference_count": self.inference_count,
            "config": self.config.model_dump(),
        }
