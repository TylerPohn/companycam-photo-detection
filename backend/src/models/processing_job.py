"""Processing job model for tracking async message processing"""

from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel
import enum


class ProcessingStatus(str, enum.Enum):
    """Processing job status lifecycle"""
    QUEUED = "queued"
    RECEIVED = "received"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(BaseModel):
    """
    Processing job model for tracking async photo detection processing.
    Tracks the lifecycle of messages from queue to completion.
    """

    __tablename__ = "processing_jobs"

    photo_id = Column(
        UUID(as_uuid=True), ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    queue_name = Column(String(100), nullable=True)
    message_id = Column(String(255), nullable=True, index=True)
    status = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    processing_time_ms = Column(Integer, nullable=True)

    # Relationships
    photo = relationship("Photo", back_populates="processing_jobs")

    def __repr__(self):
        return f"<ProcessingJob(id={self.id}, photo_id={self.photo_id}, status={self.status})>"
