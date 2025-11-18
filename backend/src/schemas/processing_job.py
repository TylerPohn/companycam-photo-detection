"""Processing job schemas for API requests/responses"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ProcessingJobBase(BaseModel):
    """Base schema for processing jobs"""
    photo_id: UUID
    queue_name: Optional[str] = None
    message_id: Optional[str] = None
    status: str
    retry_count: int = 0


class ProcessingJobCreate(ProcessingJobBase):
    """Schema for creating a new processing job"""
    pass


class ProcessingJobUpdate(BaseModel):
    """Schema for updating a processing job"""
    status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: Optional[int] = None
    processing_time_ms: Optional[int] = None


class ProcessingJobResponse(ProcessingJobBase):
    """Schema for processing job API responses"""
    id: UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    processing_time_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PhotoDetectionMessage(BaseModel):
    """Schema for photo detection queue messages"""
    message_id: str = Field(..., description="Unique message ID from queue")
    photo_id: UUID = Field(..., description="UUID of the photo to process")
    user_id: UUID = Field(..., description="UUID of the user who uploaded the photo")
    project_id: UUID = Field(..., description="UUID of the project")
    s3_url: str = Field(..., description="S3 URL of the photo")
    s3_key: str = Field(..., description="S3 key path")
    detection_types: list[str] = Field(
        default=["damage", "material"],
        description="Types of detection to run"
    )
    priority: str = Field(default="normal", description="Message priority level")
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata (file_size, dimensions, timestamp)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Message creation timestamp"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message_id": "550e8400-e29b-41d4-a716-446655440000",
                "photo_id": "550e8400-e29b-41d4-a716-446655440001",
                "user_id": "550e8400-e29b-41d4-a716-446655440002",
                "project_id": "550e8400-e29b-41d4-a716-446655440003",
                "s3_url": "https://companycam-photos.s3.amazonaws.com/project/2025/11/17/photo.jpg",
                "s3_key": "project_id/2025/11/17/photo.jpg",
                "detection_types": ["damage", "material"],
                "priority": "normal",
                "metadata": {
                    "file_size": 2097152,
                    "dimensions": {"width": 4000, "height": 3000},
                    "timestamp": "2025-11-17T10:30:00Z"
                },
                "created_at": "2025-11-17T10:30:00Z"
            }
        }
