"""Configuration for damage detection models"""

from typing import Dict, Any
from pydantic import BaseModel, Field


class DetectorConfig(BaseModel):
    """Configuration for YOLOv8 damage detector"""
    model_config = {"protected_namespaces": ()}

    model_path: str = Field(default="models/damage_yolov8.pt", description="Path to YOLOv8 model weights")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    iou_threshold: float = Field(default=0.45, ge=0.0, le=1.0, description="NMS IoU threshold")
    input_size: int = Field(default=640, description="Model input size (square)")
    max_detections: int = Field(default=100, description="Maximum detections per image")
    device: str = Field(default="cpu", description="Device for inference: 'cpu' or 'cuda'")


class SegmenterConfig(BaseModel):
    """Configuration for U-Net segmentation model"""
    model_config = {"protected_namespaces": ()}

    model_path: str = Field(default="models/damage_unet.pt", description="Path to U-Net model weights")
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    input_size: int = Field(default=512, description="Model input size (square)")
    device: str = Field(default="cpu", description="Device for inference: 'cpu' or 'cuda'")


class SeverityClassifierConfig(BaseModel):
    """Configuration for severity classifier (ResNet50)"""
    model_config = {"protected_namespaces": ()}

    model_path: str = Field(default="models/severity_resnet50.pt", description="Path to classifier weights")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    input_size: int = Field(default=224, description="Model input size (square)")
    device: str = Field(default="cpu", description="Device for inference: 'cpu' or 'cuda'")


class DamageDetectionConfig(BaseModel):
    """Main configuration for damage detection pipeline"""
    model_config = {"protected_namespaces": ()}

    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    segmenter: SegmenterConfig = Field(default_factory=SegmenterConfig)
    severity_classifier: SeverityClassifierConfig = Field(default_factory=SeverityClassifierConfig)

    model_version: str = Field(default="damage-v1.2.0", description="Overall model version")
    enable_segmentation: bool = Field(default=True, description="Enable segmentation mask generation")
    enable_severity: bool = Field(default=True, description="Enable severity classification")

    # Performance settings
    batch_size: int = Field(default=1, ge=1, le=32, description="Batch size for inference")
    max_image_dimension: int = Field(default=4096, description="Max image dimension before downsampling")

    # S3 settings for mask storage
    s3_bucket: str = Field(default="companycam-damage-masks", description="S3 bucket for mask storage")
    s3_prefix: str = Field(default="masks/", description="S3 prefix for mask files")

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return self.model_dump()


# Default configuration instance
default_config = DamageDetectionConfig()
