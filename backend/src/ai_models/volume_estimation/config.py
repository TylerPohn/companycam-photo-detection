"""Volume Estimation Engine Configuration"""

import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class DepthEstimationConfig(BaseModel):
    """Configuration for depth estimation model (MiDaS/DPT)"""

    model_type: str = Field(default="DPT_Large", description="DPT model variant")
    model_path: Optional[str] = Field(default=None, description="Path to model weights")
    input_size: int = Field(default=384, description="Model input size")
    normalize: bool = Field(default=True, description="Normalize depth maps")
    optimize: bool = Field(default=True, description="Optimize model for inference")
    device: str = Field(default="cuda", description="Device to run inference on")

    class Config:
        frozen = True


class MaterialSegmentationConfig(BaseModel):
    """Configuration for material segmentation model"""

    model_type: str = Field(default="deeplabv3_resnet50", description="Segmentation model")
    model_path: Optional[str] = Field(default=None, description="Path to model weights")
    input_size: tuple = Field(default=(512, 512), description="Input image size")
    num_classes: int = Field(default=5, description="Number of material classes")
    device: str = Field(default="cuda", description="Device to run inference on")
    threshold: float = Field(default=0.5, description="Segmentation confidence threshold")

    # Material class mappings
    material_classes: Dict[int, str] = Field(
        default={
            0: "background",
            1: "gravel",
            2: "mulch",
            3: "sand",
            4: "other_material"
        }
    )

    class Config:
        frozen = True


class ScaleDetectionConfig(BaseModel):
    """Configuration for scale reference detection"""

    model_type: str = Field(default="yolov8n", description="YOLOv8 model size")
    model_path: Optional[str] = Field(default=None, description="Path to model weights")
    confidence_threshold: float = Field(default=0.5, description="Detection confidence threshold")
    device: str = Field(default="cuda", description="Device to run inference on")

    # Reference object classes
    reference_classes: Dict[str, int] = Field(
        default={
            "person": 0,
            "measuring_tape": 1,
            "ruler": 2,
            "car": 3,
            "wheel": 4
        }
    )

    class Config:
        frozen = True


class VolumeCalculationConfig(BaseModel):
    """Configuration for volume calculation"""

    # Unit conversion factors (to cubic meters)
    unit_conversions: Dict[str, float] = Field(
        default={
            "cubic_meters": 1.0,
            "cubic_yards": 0.764555,
            "cubic_feet": 0.0283168,
            "liters": 0.001,
            "gallons": 0.00378541
        }
    )

    default_unit: str = Field(default="cubic_yards", description="Default output unit")

    # Scale reference defaults (in cm)
    reference_heights: Dict[str, float] = Field(
        default={
            "person": 170.0,
            "car": 150.0,
            "wheel": 65.0
        }
    )

    # Calculation parameters
    smoothing_kernel_size: int = Field(default=5, description="Depth map smoothing kernel")
    depth_max_meters: float = Field(default=10.0, description="Maximum depth in meters")
    pixel_area_threshold: int = Field(default=1000, description="Minimum material pixel area")

    class Config:
        frozen = True


class ConfidenceConfig(BaseModel):
    """Configuration for confidence scoring"""

    # Confidence weights for different components
    depth_weight: float = Field(default=0.35, description="Weight for depth estimation confidence")
    segmentation_weight: float = Field(default=0.30, description="Weight for segmentation confidence")
    scale_weight: float = Field(default=0.35, description="Weight for scale detection confidence")

    # Confidence thresholds
    low_confidence_threshold: float = Field(default=0.7, description="Below this requires user confirmation")
    high_confidence_threshold: float = Field(default=0.85, description="Above this is high confidence")

    # Uncertainty parameters
    confidence_interval_multiplier: float = Field(default=1.96, description="95% confidence interval")

    class Config:
        frozen = True


class VolumeEstimationConfig(BaseModel):
    """Master configuration for Volume Estimation Engine"""

    # Model version
    model_version: str = Field(default="volume-v1.0.0", description="Volume estimation model version")

    # Sub-configurations
    depth_estimation: DepthEstimationConfig = Field(default_factory=DepthEstimationConfig)
    material_segmentation: MaterialSegmentationConfig = Field(default_factory=MaterialSegmentationConfig)
    scale_detection: ScaleDetectionConfig = Field(default_factory=ScaleDetectionConfig)
    volume_calculation: VolumeCalculationConfig = Field(default_factory=VolumeCalculationConfig)
    confidence: ConfidenceConfig = Field(default_factory=ConfidenceConfig)

    # Performance settings
    max_image_size: int = Field(default=2048, description="Maximum image dimension")
    target_latency_ms: int = Field(default=550, description="Target P95 latency")
    enable_caching: bool = Field(default=True, description="Enable result caching")
    cache_ttl_seconds: int = Field(default=3600, description="Cache TTL in seconds")

    # S3 settings for depth map storage
    s3_bucket: str = Field(default=os.getenv("S3_BUCKET", "companycam-photos"), description="S3 bucket for depth maps")
    s3_depth_map_prefix: str = Field(default="depth_maps/", description="S3 prefix for depth maps")

    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable Prometheus metrics")
    log_predictions: bool = Field(default=True, description="Log prediction details")

    class Config:
        frozen = True

    def get_device(self) -> str:
        """Get the compute device (cuda or cpu)"""
        import torch
        if self.depth_estimation.device == "cuda" and torch.cuda.is_available():
            return "cuda"
        return "cpu"


# Default configuration instance
default_config = VolumeEstimationConfig()
