"""Configuration for material detection models"""

from typing import Dict, Any
from pydantic import BaseModel, Field


class DetectorConfig(BaseModel):
    """Configuration for YOLOv8 material detector"""
    model_config = {"protected_namespaces": ()}

    model_path: str = Field(default="models/material_yolov8.pt", description="Path to YOLOv8 model weights")
    confidence_threshold: float = Field(default=0.65, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0, description="NMS IoU threshold")
    input_size: int = Field(default=640, description="Model input size (square)")
    max_detections: int = Field(default=100, description="Maximum detections per image")
    device: str = Field(default="cpu", description="Device for inference: 'cpu' or 'cuda'")


class CounterConfig(BaseModel):
    """Configuration for density estimation counter"""
    model_config = {"protected_namespaces": ()}

    model_path: str = Field(default="models/density_cnn.pt", description="Path to density estimation model weights")
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    input_size: int = Field(default=256, description="Model input size (square)")
    device: str = Field(default="cpu", description="Device for inference: 'cpu' or 'cuda'")
    merge_distance_threshold: int = Field(default=50, description="Pixel distance for merging nearby detections")


class BrandDetectorConfig(BaseModel):
    """Configuration for OCR brand detector"""
    model_config = {"protected_namespaces": ()}

    ocr_engine: str = Field(default="tesseract", description="OCR engine: 'tesseract', 'textract', or 'cloud_vision'")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    fuzzy_match_threshold: int = Field(default=80, ge=0, le=100, description="Fuzzy string match threshold")
    roi_expand_pixels: int = Field(default=20, description="Pixels to expand ROI for OCR")
    aws_region: str = Field(default="us-west-2", description="AWS region for Textract")


class ValidatorConfig(BaseModel):
    """Configuration for material quantity validator"""
    model_config = {"protected_namespaces": ()}

    underage_threshold_pct: float = Field(default=5.0, ge=0.0, description="Threshold % for underage alert")
    overage_threshold_pct: float = Field(default=5.0, ge=0.0, description="Threshold % for overage alert")
    enable_alerts: bool = Field(default=True, description="Enable alert generation")


class MaterialDetectionConfig(BaseModel):
    """Main configuration for material detection pipeline"""
    model_config = {"protected_namespaces": ()}

    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    counter: CounterConfig = Field(default_factory=CounterConfig)
    brand_detector: BrandDetectorConfig = Field(default_factory=BrandDetectorConfig)
    validator: ValidatorConfig = Field(default_factory=ValidatorConfig)

    model_version: str = Field(default="material-v1.1.0", description="Overall model version")
    enable_counting: bool = Field(default=True, description="Enable density estimation counting")
    enable_brand_detection: bool = Field(default=True, description="Enable brand detection via OCR")

    # Performance settings
    batch_size: int = Field(default=1, ge=1, le=32, description="Batch size for inference")
    max_image_dimension: int = Field(default=4096, description="Max image dimension before downsampling")
    target_latency_ms: int = Field(default=450, description="Target P95 inference latency")

    # Material database path
    materials_db_path: str = Field(default="backend/data/materials.json", description="Path to materials database")
    brands_db_path: str = Field(default="backend/data/brands.json", description="Path to brands database")

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return self.model_dump()


# Default configuration instance
default_config = MaterialDetectionConfig()
