"""Detection result schemas for unified API responses"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID


class TagSchema(BaseModel):
    """Schema for individual tag in detection results"""
    tag: str = Field(..., description="Tag name")
    source: str = Field(..., description="Tag source: ai or user")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    engines: List[str] = Field(default_factory=list, description="Detection engines that contributed to this tag")

    model_config = ConfigDict(from_attributes=True)


class UserConfirmationSchema(BaseModel):
    """Schema for user confirmation status"""
    status: str = Field(..., description="Status: pending, confirmed, corrected")
    confirmed_by: Optional[UUID] = Field(None, description="User ID who confirmed")
    confirmed_at: Optional[datetime] = Field(None, description="Confirmation timestamp")
    corrections: Optional[Dict[str, Any]] = Field(None, description="User corrections if any")

    model_config = ConfigDict(from_attributes=True)


class DetectionSummarySchema(BaseModel):
    """Schema for detection summary"""
    has_damage: bool = Field(False, description="Whether damage was detected")
    damage_severity: Optional[str] = Field(None, description="Damage severity level")
    materials_detected: int = Field(0, description="Number of materials detected")
    volume_estimated: bool = Field(False, description="Whether volume was estimated")

    model_config = ConfigDict(from_attributes=True)


class DetectionMetadataSchema(BaseModel):
    """Schema for detection metadata"""
    project_id: UUID = Field(..., description="Project ID")
    user_id: UUID = Field(..., description="User ID who uploaded photo")
    processing_region: str = Field(..., description="AWS region where processing occurred")
    api_version: str = Field(default="v1", description="API version")

    model_config = ConfigDict(from_attributes=True)


class AggregatedDetectionResultSchema(BaseModel):
    """
    Unified detection result schema combining all detection types.
    This is the main response schema for detection results.
    """
    photo_id: UUID = Field(..., description="Photo ID")
    detection_id: UUID = Field(..., description="Detection ID")
    detected_at: datetime = Field(..., description="Detection timestamp")
    processing_time_ms: int = Field(..., description="Total processing time in milliseconds")

    model_versions: Dict[str, str] = Field(
        default_factory=dict,
        description="Model versions for each detection type"
    )

    detections: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detection results by type (damage, material, volume)"
    )

    aggregate_tags: List[TagSchema] = Field(
        default_factory=list,
        description="Aggregated tags from all detection engines"
    )

    summary: DetectionSummarySchema = Field(
        ...,
        description="High-level summary of all detections"
    )

    user_confirmation: UserConfirmationSchema = Field(
        ...,
        description="User confirmation status"
    )

    metadata: DetectionMetadataSchema = Field(
        ...,
        description="Additional metadata about the detection"
    )

    model_config = ConfigDict(from_attributes=True)


class DetectionResultResponseSchema(BaseModel):
    """Response schema for detection result retrieval"""
    id: UUID = Field(..., description="Detection ID")
    photo_id: UUID = Field(..., description="Photo ID")
    detection_type: str = Field(..., description="Detection type: damage, material, or volume")
    model_version: Optional[str] = Field(None, description="Model version used")
    results: Dict[str, Any] = Field(..., description="Detection results")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Overall confidence")
    processing_time_ms: Optional[int] = Field(None, description="Processing time in ms")
    user_confirmed: bool = Field(False, description="Whether user confirmed")
    user_feedback: Optional[Dict[str, Any]] = Field(None, description="User feedback")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class DetectionListResponseSchema(BaseModel):
    """Response schema for list of detections"""
    detections: List[DetectionResultResponseSchema] = Field(..., description="List of detections")
    total: int = Field(..., description="Total number of detections")
    page: int = Field(1, description="Current page number")
    page_size: int = Field(50, description="Items per page")

    model_config = ConfigDict(from_attributes=True)
