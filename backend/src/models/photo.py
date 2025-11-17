"""Photo model"""

from sqlalchemy import Column, String, Integer, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Photo(BaseModel):
    """
    Photo model representing uploaded construction photos.
    Photos belong to a user and project, and can have multiple detections and tags.
    """

    __tablename__ = "photos"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    s3_url = Column(Text, nullable=False)
    s3_key = Column(String(500), nullable=True, unique=True)
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(50), nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    exif_data = Column(JSONB, nullable=True)  # Camera metadata, GPS, timestamp
    uploaded_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="photos")
    project = relationship("Project", back_populates="photos")
    detections = relationship(
        "Detection", back_populates="photo", cascade="all, delete-orphan"
    )
    tags = relationship("Tag", back_populates="photo", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Photo(id={self.id}, s3_key={self.s3_key})>"
