"""Material Segmentation for loose materials (gravel, mulch, sand)"""

import logging
import time
from typing import Tuple, Dict
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class MaterialSegmenter:
    """
    Material segmentation using U-Net or DeepLabv3.
    Segments loose materials (gravel, mulch, sand) from images.
    """

    def __init__(self, config):
        """
        Initialize material segmenter.

        Args:
            config: MaterialSegmentationConfig instance
        """
        self.config = config
        self.model = None
        self.device = config.device
        self._inference_count = 0
        self._total_inference_time = 0.0

        logger.info(f"MaterialSegmenter initialized with model_type={config.model_type}, device={config.device}")

    def load_model(self):
        """Load the material segmentation model"""
        try:
            import torch

            # Check device availability
            if self.device == "cuda" and not torch.cuda.is_available():
                logger.warning("CUDA not available, falling back to CPU")
                self.device = "cpu"

            logger.info(f"Loading material segmentation model: {self.config.model_type}")

            # Mock model for development - in production this would be:
            # self.model = torch.hub.load('pytorch/vision', self.config.model_type, pretrained=True)
            # For now, use a simple mock
            self.model = MockSegmentationModel(self.config.model_type, self.config.num_classes, self.device)

            self.model.eval()

            logger.info(f"Material segmentation model loaded successfully on {self.device}")

        except Exception as e:
            logger.error(f"Failed to load material segmentation model: {e}")
            raise

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for segmentation.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format

        Returns:
            Preprocessed image
        """
        # Resize to model input size
        target_h, target_w = self.config.input_size
        resized = cv2.resize(image, (target_w, target_h), interpolation=cv2.INTER_LINEAR)

        # Normalize to [0, 1]
        normalized = resized.astype(np.float32) / 255.0

        # Apply ImageNet normalization
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        normalized = (normalized - mean) / std

        return normalized

    def segment(self, image: np.ndarray) -> Tuple[np.ndarray, str, dict]:
        """
        Segment material from image.

        Args:
            image: Input image as numpy array (H, W, C) in RGB format

        Returns:
            Tuple of (segmentation_mask, material_type, metadata)
            - segmentation_mask: Binary mask (H, W) with material pixels
            - material_type: Detected material type (gravel, mulch, sand)
            - metadata: Dict with inference time, confidence, etc.
        """
        if self.model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        start_time = time.time()

        try:
            original_h, original_w = image.shape[:2]

            # Preprocess image
            preprocessed = self.preprocess_image(image)

            # Run inference
            class_map, class_probs = self.model.predict(preprocessed)

            # Resize segmentation to original image size
            class_map = cv2.resize(
                class_map.astype(np.uint8),
                (original_w, original_h),
                interpolation=cv2.INTER_NEAREST
            )

            # Identify dominant material class (exclude background)
            material_type, material_confidence = self._identify_material(class_map, class_probs)

            # Create binary mask for material
            mask = self._create_material_mask(class_map, material_type)

            # Post-process mask
            mask = self._postprocess_mask(mask)

            inference_time = (time.time() - start_time) * 1000  # ms

            # Update stats
            self._inference_count += 1
            self._total_inference_time += inference_time

            metadata = {
                "inference_time_ms": round(inference_time, 2),
                "model_type": self.config.model_type,
                "material_confidence": round(material_confidence, 3),
                "mask_coverage": round(mask.sum() / mask.size, 3),
                "material_pixel_count": int(mask.sum()),
                "class_distribution": self._compute_class_distribution(class_map)
            }

            logger.debug(
                f"Material segmentation completed in {inference_time:.2f}ms - "
                f"material={material_type}, confidence={material_confidence:.2f}"
            )

            return mask, material_type, metadata

        except Exception as e:
            logger.error(f"Material segmentation failed: {e}")
            raise

    def _identify_material(self, class_map: np.ndarray, class_probs: np.ndarray) -> Tuple[str, float]:
        """
        Identify the dominant material type from segmentation.

        Args:
            class_map: Class prediction map (H, W)
            class_probs: Class probabilities (H, W, num_classes)

        Returns:
            Tuple of (material_type, confidence)
        """
        # Count pixels for each class (excluding background)
        class_counts = {}
        for class_id, class_name in self.config.material_classes.items():
            if class_name != "background":
                count = (class_map == class_id).sum()
                class_counts[class_name] = count

        # Find dominant material
        if not class_counts or max(class_counts.values()) == 0:
            return "unknown", 0.0

        dominant_material = max(class_counts, key=class_counts.get)

        # Calculate confidence as average probability in material region
        material_class_id = [k for k, v in self.config.material_classes.items() if v == dominant_material][0]
        material_mask = (class_map == material_class_id)

        if material_mask.sum() > 0:
            confidence = class_probs[:, :, material_class_id][material_mask].mean()
        else:
            confidence = 0.0

        return dominant_material, float(confidence)

    def _create_material_mask(self, class_map: np.ndarray, material_type: str) -> np.ndarray:
        """
        Create binary mask for specific material type.

        Args:
            class_map: Class prediction map
            material_type: Target material type

        Returns:
            Binary mask
        """
        # Get class ID for material
        material_class_id = None
        for class_id, class_name in self.config.material_classes.items():
            if class_name == material_type:
                material_class_id = class_id
                break

        if material_class_id is None:
            return np.zeros_like(class_map, dtype=np.uint8)

        # Create binary mask
        mask = (class_map == material_class_id).astype(np.uint8)

        return mask

    def _postprocess_mask(self, mask: np.ndarray) -> np.ndarray:
        """
        Clean up segmentation mask using morphological operations.

        Args:
            mask: Binary mask

        Returns:
            Cleaned mask
        """
        # Remove small noise
        kernel_small = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_small)

        # Fill small holes
        kernel_large = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_large)

        # Keep only the largest connected component
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

        if num_labels > 1:
            # Find largest component (excluding background)
            largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            mask = (labels == largest_label).astype(np.uint8)

        return mask

    def _compute_class_distribution(self, class_map: np.ndarray) -> Dict[str, float]:
        """
        Compute distribution of classes in segmentation.

        Args:
            class_map: Class prediction map

        Returns:
            Dict mapping class names to pixel percentages
        """
        total_pixels = class_map.size
        distribution = {}

        for class_id, class_name in self.config.material_classes.items():
            count = (class_map == class_id).sum()
            distribution[class_name] = round(count / total_pixels, 4)

        return distribution

    def get_stats(self) -> dict:
        """Get material segmenter statistics"""
        avg_time = self._total_inference_time / max(self._inference_count, 1)

        return {
            "inference_count": self._inference_count,
            "total_inference_time_ms": round(self._total_inference_time, 2),
            "average_inference_time_ms": round(avg_time, 2),
            "model_type": self.config.model_type,
            "device": self.device
        }


class MockSegmentationModel:
    """
    Mock segmentation model for development and testing.
    In production, this would be replaced with actual U-Net/DeepLabv3 model.
    """

    def __init__(self, model_type: str, num_classes: int, device: str):
        self.model_type = model_type
        self.num_classes = num_classes
        self.device = device
        logger.info(f"MockSegmentationModel initialized (model_type={model_type}, num_classes={num_classes})")

    def eval(self):
        """Set model to evaluation mode"""
        pass

    def predict(self, image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generate mock segmentation using simple heuristics.

        Args:
            image: Preprocessed image

        Returns:
            Tuple of (class_map, class_probabilities)
        """
        h, w = image.shape[:2]

        # Denormalize for processing
        mean = np.array([0.485, 0.456, 0.406])
        std = np.array([0.229, 0.224, 0.225])
        image_denorm = image * std + mean
        image_denorm = np.clip(image_denorm * 255, 0, 255).astype(np.uint8)

        # Convert to grayscale
        gray = cv2.cvtColor(image_denorm, cv2.COLOR_RGB2GRAY)

        # Use texture/color analysis for simple segmentation
        # This is a very simple heuristic - real models use deep learning

        # Detect material region using thresholding
        # Assume material is in center-bottom portion of image
        mask = np.zeros((h, w), dtype=np.uint8)

        # Create a region in the bottom 60% of image
        y_start = int(h * 0.4)
        mask[y_start:, :] = 1

        # Refine using color/intensity
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        material_mask = (thresh < 200) & (mask == 1)

        # Create class map
        class_map = np.zeros((h, w), dtype=np.int32)

        # Randomly assign material type (gravel=1, mulch=2, sand=3)
        # In reality, this would be based on texture/color analysis
        material_type = np.random.choice([1, 2, 3])  # gravel, mulch, or sand
        class_map[material_mask] = material_type

        # Create class probabilities
        class_probs = np.zeros((h, w, self.num_classes), dtype=np.float32)
        class_probs[:, :, 0] = 0.8  # background default
        class_probs[material_mask, 0] = 0.1
        class_probs[material_mask, material_type] = 0.85

        return class_map, class_probs
