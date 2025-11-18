"""Database models package"""

from src.models.base import BaseModel
from src.models.organization import Organization
from src.models.user import User
from src.models.project import Project
from src.models.photo import Photo, PhotoStatus
from src.models.detection import Detection
from src.models.tag import Tag
from src.models.processing_job import ProcessingJob, ProcessingStatus

# Export all models
__all__ = [
    "BaseModel",
    "Organization",
    "User",
    "Project",
    "Photo",
    "PhotoStatus",
    "Detection",
    "Tag",
    "ProcessingJob",
    "ProcessingStatus",
]
