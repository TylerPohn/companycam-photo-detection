"""User feedback schemas for detection confirmations and corrections"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID


class FeedbackCreateSchema(BaseModel):
    """Schema for creating user feedback on detection results"""
    detection_id: UUID = Field(..., description="Detection ID to provide feedback on")
    feedback_type: str = Field(
        ...,
        description="Feedback type: confirmed, rejected, or corrected",
        pattern="^(confirmed|rejected|corrected)$"
    )
    corrections: Optional[Dict[str, Any]] = Field(
        None,
        description="Corrected values if feedback_type is 'corrected'"
    )
    comments: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional user comments"
    )

    model_config = ConfigDict(from_attributes=True)


class FeedbackResponseSchema(BaseModel):
    """Schema for feedback response"""
    id: UUID = Field(..., description="Feedback ID")
    detection_id: UUID = Field(..., description="Detection ID")
    user_id: Optional[UUID] = Field(None, description="User who provided feedback")
    feedback_type: str = Field(..., description="Feedback type")
    corrections: Optional[Dict[str, Any]] = Field(None, description="Corrections")
    comments: Optional[str] = Field(None, description="Comments")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(from_attributes=True)


class FeedbackStatsSchema(BaseModel):
    """Schema for feedback statistics"""
    model_version: str = Field(..., description="Model version")
    total_feedback: int = Field(..., description="Total feedback count")
    confirmed: int = Field(..., description="Number of confirmations")
    rejected: int = Field(..., description="Number of rejections")
    corrected: int = Field(..., description="Number of corrections")
    accuracy_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Accuracy rate (confirmed / total)"
    )

    model_config = ConfigDict(from_attributes=True)
