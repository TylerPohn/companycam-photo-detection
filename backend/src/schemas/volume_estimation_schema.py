"""Volume Estimation Response Schemas"""

from typing import Optional, Dict
from pydantic import BaseModel, Field, field_validator


class VolumeRange(BaseModel):
    """Volume range with min/max bounds"""

    min: float = Field(..., ge=0, description="Minimum estimated volume")
    max: float = Field(..., ge=0, description="Maximum estimated volume")

    @field_validator("max")
    @classmethod
    def max_must_be_greater_than_min(cls, v, info):
        if "min" in info.data and v < info.data["min"]:
            raise ValueError("max must be >= min")
        return v


class ScaleReference(BaseModel):
    """Scale reference object information"""

    type: str = Field(..., description="Type of reference object (person, measuring_tape, etc.)")
    confidence: float = Field(..., ge=0, le=1, description="Detection confidence")
    estimated_height_cm: Optional[float] = Field(None, description="Estimated height in cm")
    estimated_diameter_cm: Optional[float] = Field(None, description="Estimated diameter in cm")


class ConfidenceBreakdown(BaseModel):
    """Confidence scores for each pipeline component"""

    depth_estimation: float = Field(..., ge=0, le=1, description="Depth estimation confidence")
    material_detection: float = Field(..., ge=0, le=1, description="Material detection confidence")
    scale_detection: float = Field(..., ge=0, le=1, description="Scale detection confidence")


class ComponentTimings(BaseModel):
    """Processing time for each pipeline component"""

    depth_estimation: float = Field(..., ge=0, description="Depth estimation time (ms)")
    material_segmentation: float = Field(..., ge=0, description="Material segmentation time (ms)")
    scale_detection: float = Field(..., ge=0, description="Scale detection time (ms)")
    volume_calculation: float = Field(..., ge=0, description="Volume calculation time (ms)")


class VolumeEstimationResponse(BaseModel):
    """Complete volume estimation response"""

    material: str = Field(..., description="Detected material type (gravel, mulch, sand)")
    estimated_volume: float = Field(..., ge=0, description="Estimated volume in specified unit")
    unit: str = Field(..., description="Unit of measurement (cubic_yards, cubic_feet, etc.)")
    confidence: float = Field(..., ge=0, le=1, description="Overall confidence score")
    requires_confirmation: bool = Field(..., description="Whether user confirmation is needed")
    volume_range: VolumeRange = Field(..., description="Volume uncertainty range")
    depth_map: Optional[str] = Field(None, description="URL to depth map visualization")
    scale_reference: Optional[ScaleReference] = Field(None, description="Detected scale reference")
    calculation_method: str = Field(..., description="Method used for volume calculation")
    processing_time_ms: float = Field(..., ge=0, description="Total processing time in milliseconds")
    model_version: str = Field(..., description="Model version identifier")
    confidence_breakdown: ConfidenceBreakdown = Field(..., description="Component confidence scores")
    component_timings_ms: Optional[ComponentTimings] = Field(
        None, description="Processing time breakdown by component"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "material": "gravel",
                "estimated_volume": 2.5,
                "unit": "cubic_yards",
                "confidence": 0.75,
                "requires_confirmation": True,
                "volume_range": {
                    "min": 2.1,
                    "max": 2.9
                },
                "depth_map": "s3://bucket/depth/photo123.png",
                "scale_reference": {
                    "type": "person",
                    "confidence": 0.82,
                    "estimated_height_cm": 170.0,
                    "estimated_diameter_cm": None
                },
                "calculation_method": "depth_map_person",
                "processing_time_ms": 520.0,
                "model_version": "volume-v1.0.0",
                "confidence_breakdown": {
                    "depth_estimation": 0.88,
                    "material_detection": 0.92,
                    "scale_detection": 0.75
                },
                "component_timings_ms": {
                    "depth_estimation": 220.0,
                    "material_segmentation": 150.0,
                    "scale_detection": 100.0,
                    "volume_calculation": 50.0
                }
            }
        }


class VolumeEstimationRequest(BaseModel):
    """Volume estimation request"""

    photo_id: str = Field(..., description="Photo ID")
    photo_url: str = Field(..., description="URL to photo in S3")
    save_depth_map: bool = Field(default=True, description="Whether to save depth map visualization")
    unit: Optional[str] = Field(
        default="cubic_yards",
        description="Desired unit for volume (cubic_yards, cubic_feet, cubic_meters)"
    )


class VolumeEstimationError(BaseModel):
    """Volume estimation error response"""

    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    photo_id: Optional[str] = Field(None, description="Photo ID if available")
    processing_time_ms: Optional[float] = Field(None, description="Processing time before error")
