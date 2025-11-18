"""Scale Reference Detection for real-world measurement calibration"""

import logging
import time
import json
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class ScaleDetector:
    """
    Detect scale reference objects (person, measuring tape, etc.) in images
    to establish real-world measurements for volume calculation.
    """

    def __init__(self, config):
        """
        Initialize scale detector.

        Args:
            config: ScaleDetectionConfig instance
        """
        self.config = config
        self.model = None
        self.device = config.device
        self.reference_data = None
        self._inference_count = 0
        self._total_inference_time = 0.0

        logger.info(f"ScaleDetector initialized with model_type={config.model_type}, device={config.device}")

    def load_model(self):
        """Load the scale detection model (YOLOv8)"""
        try:
            import torch

            # Check device availability
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = "cpu"

            logger.info(f"Loading scale detection model: {self.config.model_type}")

            # Mock model for development - in production this would be:
            # from ultralytics import YOLO
            # self.model = YOLO(self.config.model_type)
            # For now, use a simple mock
            self.model = MockYOLOModel(self.config.model_type, self.device)

            # Load reference object database
            self._load_reference_database()

            logger.info(f"Scale detection model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load scale detection model: {e}")
            raise

    def _load_reference_database(self):
        """Load reference object database"""
        try:
            # Load from data directory
            data_path = Path(__file__).parent.parent.parent.parent / "data" / "reference_objects.json"

            if data_path.exists():
                with open(data_path, 'r') as f:
                    self.reference_data = json.load(f)
                logger.info(f"Loaded reference object database from {data_path}")
            else:
                logger.warning(f"Reference database not found at {data_path}, using defaults")
                self.reference_data = self._get_default_reference_data()

        except Exception as e:
            logger.error(f"Failed to load reference database: {e}")
            self.reference_data = self._get_default_reference_data()

    def _get_default_reference_data(self) -> dict:
        """Get default reference object data"""
        return {
            "reference_objects": {
                "person": {"height_cm": 170.0, "confidence_factor": 0.85},
                "car": {"height_cm": 150.0, "confidence_factor": 0.70},
                "wheel": {"diameter_cm": 65.0, "confidence_factor": 0.75}
            }
        }

    def detect_scale_reference(
        self, image: np.ndarray, depth_map: Optional[np.ndarray] = None
    ) -> Tuple[Optional[Dict], dict]:
        """
        Detect scale reference objects in image.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format
            depth_map: Optional depth map for improved scale estimation

        Returns:
            Tuple of (scale_reference, metadata)
            - scale_reference: Dict with reference info (type, height, confidence) or None
            - metadata: Dict with inference time, detections, etc.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        start_time = time.time()

        try:
            # Run object detection
            detections = self.model.predict(image, conf_threshold=self.config.confidence_threshold)

            # Find best scale reference from detections
            scale_reference = self._select_best_reference(detections, image, depth_map)

            inference_time = (time.time() - start_time) * 1000  # ms

            # Update stats
            self._inference_count += 1
            self._total_inference_time += inference_time

            metadata = {
                "inference_time_ms": round(inference_time, 2),
                "model_type": self.config.model_type,
                "num_detections": len(detections),
                "detection_classes": [d["class"] for d in detections],
                "has_scale_reference": scale_reference is not None
            }

            if scale_reference:
                logger.debug(
                    f"Scale reference detected: type={scale_reference['type']}, "
                    f"confidence={scale_reference['confidence']:.2f}"
                )
            else:
                logger.debug("No suitable scale reference found in image")

            return scale_reference, metadata

        except Exception as e:
            logger.error(f"Scale reference detection failed: {e}")
            raise

    def _select_best_reference(
        self,
        detections: List[Dict],
        image: np.ndarray,
        depth_map: Optional[np.ndarray]
    ) -> Optional[Dict]:
        """
        Select the best scale reference from detections.

        Args:
            detections: List of detected objects
            image: Original image
            depth_map: Optional depth map

        Returns:
            Best scale reference dict or None
        """
        if not detections:
            return None

        # Priority order: measuring_tape > person > wheel > car
        priority_order = ["measuring_tape", "person", "wheel", "car"]

        # Find highest priority reference
        best_reference = None
        best_priority = float('inf')

        for detection in detections:
            class_name = detection["class"]

            if class_name in priority_order:
                priority = priority_order.index(class_name)

                if priority < best_priority:
                    best_priority = priority
                    best_reference = detection

        if best_reference is None:
            return None

        # Extract scale information
        return self._extract_scale_info(best_reference, image, depth_map)

    def _extract_scale_info(
        self,
        detection: Dict,
        image: np.ndarray,
        depth_map: Optional[np.ndarray]
    ) -> Dict:
        """
        Extract scale information from detected reference object.

        Args:
            detection: Detection dict
            image: Original image
            depth_map: Optional depth map

        Returns:
            Scale reference dict
        """
        class_name = detection["class"]
        bbox = detection["bbox"]
        confidence = detection["confidence"]

        # Get reference object data
        ref_objects = self.reference_data.get("reference_objects", {})
        ref_data = ref_objects.get(class_name, {})

        # Determine reference dimension
        if "height_cm" in ref_data:
            dimension_cm = ref_data["height_cm"]
            dimension_type = "height"
        elif "diameter_cm" in ref_data:
            dimension_cm = ref_data["diameter_cm"]
            dimension_type = "diameter"
        else:
            dimension_cm = 170.0  # Default to person height
            dimension_type = "height"

        # Calculate pixel dimension from bounding box
        x1, y1, x2, y2 = bbox
        if dimension_type == "height":
            pixel_dimension = y2 - y1
        else:
            pixel_dimension = min(x2 - x1, y2 - y1)  # Use smaller dimension for diameter

        # Calculate pixels per cm
        if pixel_dimension > 0:
            pixels_per_cm = pixel_dimension / dimension_cm
        else:
            pixels_per_cm = 1.0

        # Adjust confidence based on reference quality
        ref_confidence_factor = ref_data.get("confidence_factor", 0.8)
        adjusted_confidence = confidence * ref_confidence_factor

        scale_reference = {
            "type": class_name,
            "confidence": round(adjusted_confidence, 3),
            "estimated_height_cm": dimension_cm if dimension_type == "height" else None,
            "estimated_diameter_cm": dimension_cm if dimension_type == "diameter" else None,
            "bbox": bbox,
            "pixel_dimension": pixel_dimension,
            "pixels_per_cm": pixels_per_cm,
            "dimension_type": dimension_type
        }

        # Enhance with depth information if available
        if depth_map is not None:
            scale_reference["depth_enhanced"] = True
            scale_reference = self._enhance_with_depth(scale_reference, depth_map, bbox)
        else:
            scale_reference["depth_enhanced"] = False

        return scale_reference

    def _enhance_with_depth(
        self,
        scale_reference: Dict,
        depth_map: np.ndarray,
        bbox: Tuple[int, int, int, int]
    ) -> Dict:
        """
        Enhance scale reference using depth information.

        Args:
            scale_reference: Scale reference dict
            depth_map: Depth map
            bbox: Bounding box (x1, y1, x2, y2)

        Returns:
            Enhanced scale reference
        """
        x1, y1, x2, y2 = bbox

        # Get average depth in reference region
        ref_depth = depth_map[y1:y2, x1:x2].mean()
        scale_reference["reference_depth"] = float(ref_depth)

        # Depth can help refine scale estimation
        # Objects farther away appear smaller in image
        # This is a simplified approach - real implementation would use camera calibration

        return scale_reference

    def estimate_scale_from_exif(self, image_path: str) -> Optional[Dict]:
        """
        Estimate scale from camera EXIF data (fallback method).

        Args:
            image_path: Path to image file

        Returns:
            Scale reference dict or None
        """
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            img = Image.open(image_path)
            exif = img._getexif()

            if exif is None:
                return None

            # Extract focal length and sensor size
            focal_length = None
            sensor_width = None

            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)

                if tag == "FocalLength":
                    focal_length = float(value)
                elif tag == "FocalPlaneXResolution":
                    # Simplified - real implementation would be more complex
                    sensor_width = 36.0  # Assume full-frame equivalent

            if focal_length and sensor_width:
                # Create scale reference from camera intrinsics
                return {
                    "type": "camera_intrinsics",
                    "confidence": 0.6,
                    "focal_length_mm": focal_length,
                    "sensor_width_mm": sensor_width,
                    "method": "exif_calibration"
                }

        except Exception as e:
            logger.debug(f"Failed to extract EXIF data: {e}")

        return None

    def get_stats(self) -> dict:
        """Get scale detector statistics"""
        avg_time = self._total_inference_time / max(self._inference_count, 1)

        return {
            "inference_count": self._inference_count,
            "total_inference_time_ms": round(self._total_inference_time, 2),
            "average_inference_time_ms": round(avg_time, 2),
            "model_type": self.config.model_type,
            "device": self.device
        }


class MockYOLOModel:
    """
    Mock YOLO model for development and testing.
    In production, this would be replaced with actual YOLOv8 model.
    """

    def __init__(self, model_type: str, device: str):
        self.model_type = model_type
        self.device = device
        logger.info(f"MockYOLOModel initialized (model_type={model_type})")

    def predict(self, image: np.ndarray, conf_threshold: float = 0.5) -> List[Dict]:
        """
        Generate mock object detections.

        Args:
            image: Input image
            conf_threshold: Confidence threshold

        Returns:
            List of detection dicts
        """
        h, w = image.shape[:2]

        # Simulate detecting a person in ~60% of images
        detections = []

        if np.random.random() < 0.6:
            # Create mock person detection
            # Person typically in center-left of construction photos
            person_w = int(w * 0.15)
            person_h = int(h * 0.4)
            x1 = int(w * 0.3)
            y1 = int(h * 0.3)
            x2 = x1 + person_w
            y2 = y1 + person_h

            detections.append({
                "class": "person",
                "confidence": np.random.uniform(0.7, 0.95),
                "bbox": (x1, y1, x2, y2)
            })

        return detections
