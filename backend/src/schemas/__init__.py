"""API schemas package"""

from .photo import (
    PhotoUploadUrlRequest,
    PhotoUploadUrlResponse,
    PhotoResponse,
    PhotoStatusUpdate,
)
from .processing_job import (
    ProcessingJobCreate,
    ProcessingJobUpdate,
    ProcessingJobResponse,
    PhotoDetectionMessage,
)

__all__ = [
    "PhotoUploadUrlRequest",
    "PhotoUploadUrlResponse",
    "PhotoResponse",
    "PhotoStatusUpdate",
    "ProcessingJobCreate",
    "ProcessingJobUpdate",
    "ProcessingJobResponse",
    "PhotoDetectionMessage",
]
