"""Photo API schemas"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from uuid import UUID


class PhotoUploadUrlRequest(BaseModel):
    """Request schema for generating photo upload URL"""

    project_id: UUID = Field(..., description="Project ID where photo will be uploaded")
    file_name: str = Field(..., min_length=1, max_length=255, description="Original file name")
    file_size: int = Field(..., gt=0, description="File size in bytes")
    mime_type: str = Field(..., description="MIME type of the file")

    @field_validator("mime_type")
    @classmethod
    def validate_mime_type(cls, v: str) -> str:
        """Validate MIME type is allowed"""
        allowed = {"image/jpeg", "image/png"}
        if v not in allowed:
            raise ValueError(f"MIME type must be one of {allowed}")
        return v

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        """Validate file size is within limits"""
        max_size = 50 * 1024 * 1024  # 50MB
        min_size = 1024  # 1KB
        if v > max_size:
            raise ValueError(f"File size exceeds maximum of {max_size} bytes")
        if v < min_size:
            raise ValueError(f"File size below minimum of {min_size} bytes")
        return v


class PhotoUploadUrlResponse(BaseModel):
    """Response schema for photo upload URL generation"""

    upload_id: UUID = Field(..., description="Upload ID (same as photo_id)")
    photo_id: UUID = Field(..., description="Photo ID")
    upload_url: str = Field(..., description="Pre-signed S3 upload URL")
    s3_url: str = Field(..., description="Final S3 URL where photo will be accessible")
    expires_in_seconds: int = Field(..., description="Upload URL expiration time in seconds")
    headers: Dict[str, str] = Field(..., description="Required headers for upload")


class PhotoResponse(BaseModel):
    """Response schema for photo details"""

    id: UUID = Field(..., description="Photo ID")
    user_id: UUID = Field(..., description="User ID who uploaded the photo")
    project_id: UUID = Field(..., description="Project ID")
    s3_url: str = Field(..., description="S3 URL of the photo")
    s3_key: Optional[str] = Field(None, description="S3 key")
    file_size_bytes: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type")
    width: Optional[int] = Field(None, description="Image width in pixels")
    height: Optional[int] = Field(None, description="Image height in pixels")
    exif_data: Optional[Dict[str, Any]] = Field(None, description="EXIF metadata")
    status: str = Field(..., description="Photo upload/processing status")
    uploaded_at: Optional[datetime] = Field(None, description="Upload timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


class PhotoStatusUpdate(BaseModel):
    """Request schema for updating photo status"""

    status: str = Field(..., description="New status")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        """Validate status is a valid value"""
        allowed = {"pending_upload", "uploaded", "processing", "completed", "failed"}
        if v not in allowed:
            raise ValueError(f"Status must be one of {allowed}")
        return v


class PhotoListResponse(BaseModel):
    """Response schema for list of photos"""

    photos: list[PhotoResponse] = Field(..., description="List of photos")
    total: int = Field(..., description="Total number of photos")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
