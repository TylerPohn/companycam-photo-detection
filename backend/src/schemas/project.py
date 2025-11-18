"""Project schemas"""

from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class ProjectBase(BaseModel):
    """Base project schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: str = Field(default="active", description="Project status")


class ProjectCreate(ProjectBase):
    """Project creation schema"""
    organization_id: UUID = Field(..., description="Organization UUID")


class ProjectUpdate(BaseModel):
    """Project update schema - all fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Project name")
    description: Optional[str] = Field(None, description="Project description")
    status: Optional[str] = Field(None, description="Project status")


class ProjectResponse(ProjectBase):
    """Project response schema"""
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectDetailResponse(ProjectResponse):
    """Detailed project response with additional stats"""
    photo_count: int = Field(default=0, description="Number of photos in project")
    last_photo_at: Optional[datetime] = Field(None, description="Timestamp of last photo upload")


class ProjectListResponse(BaseModel):
    """List of projects response"""
    projects: list[ProjectResponse]
    total: int = Field(..., description="Total number of projects")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=50, description="Number of items per page")
