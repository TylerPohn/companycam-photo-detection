"""Pydantic schemas for Damage Detection Engine"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class DamageType(str, Enum):
    """Types of roof damage that can be detected"""
    HAIL_DAMAGE = "hail_damage"
    WIND_DAMAGE = "wind_damage"
    MISSING_SHINGLES = "missing_shingles"
    NORMAL_SHINGLE = "normal_shingle"


class DamageSeverity(str, Enum):
    """Severity levels for detected damage"""
    MINOR = "minor"
    MODERATE = "moderate"
    SEVERE = "severe"


class BoundingBox(BaseModel):
    """Bounding box coordinates for detected damage"""
    x: int = Field(..., description="X coordinate of top-left corner")
    y: int = Field(..., description="Y coordinate of top-left corner")
    width: int = Field(..., description="Width of bounding box")
    height: int = Field(..., description="Height of bounding box")

    @field_validator('x', 'y', 'width', 'height')
    @classmethod
    def validate_positive(cls, v: int) -> int:
        """Validate that coordinates are non-negative"""
        if v < 0:
            raise ValueError("Coordinates must be non-negative")
        return v


class DamageDetection(BaseModel):
    """Individual damage detection result"""
    type: DamageType = Field(..., description="Type of damage detected")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence score")
    severity: DamageSeverity = Field(..., description="Severity level of damage")
    bounding_box: BoundingBox = Field(..., description="Bounding box coordinates")
    segmentation_mask: Optional[str] = Field(None, description="S3 URL to segmentation mask PNG")
    area_percentage: float = Field(..., ge=0.0, le=100.0, description="Percentage of image area affected")


class DamageSummary(BaseModel):
    """Summary statistics for all detections"""
    total_damage_area_percentage: float = Field(
        ..., ge=0.0, le=100.0,
        description="Total percentage of image area with damage"
    )
    damage_type_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each damage type detected"
    )


class DamageDetectionResponse(BaseModel):
    """Complete damage detection response"""
    detections: List[DamageDetection] = Field(
        default_factory=list,
        description="List of individual damage detections"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Generated tags based on detections"
    )
    summary: DamageSummary = Field(..., description="Summary statistics")
    processing_time_ms: int = Field(..., ge=0, description="Total processing time in milliseconds")
    model_version: str = Field(..., description="Model version used for detection")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")


class BatchDamageDetectionRequest(BaseModel):
    """Request schema for batch damage detection"""
    photo_urls: List[str] = Field(..., min_length=1, max_length=100, description="List of S3 photo URLs")
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum confidence threshold")
    include_segmentation: bool = Field(default=True, description="Whether to generate segmentation masks")


class BatchDamageDetectionResponse(BaseModel):
    """Response schema for batch damage detection"""
    results: Dict[str, DamageDetectionResponse] = Field(
        default_factory=dict,
        description="Detection results keyed by photo URL"
    )
    total_processing_time_ms: int = Field(..., ge=0, description="Total batch processing time")
    successful_count: int = Field(..., ge=0, description="Number of successful detections")
    failed_count: int = Field(..., ge=0, description="Number of failed detections")
    errors: Dict[str, str] = Field(
        default_factory=dict,
        description="Error messages keyed by photo URL"
    )
