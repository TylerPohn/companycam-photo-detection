"""Detection model"""

from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Detection(BaseModel):
    """
    Detection model representing AI detection results for photos.
    Stores bounding boxes, confidence scores, and user feedback.
    """

    __tablename__ = "detections"

    photo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    detection_type = Column(
        String(50), nullable=False, index=True
    )  # damage, material, volume
    model_version = Column(String(100), nullable=True)
    results = Column(JSONB, nullable=False)  # JSON with bounding boxes, classes, etc.
    confidence = Column(Float, nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    user_confirmed = Column(Boolean, default=False, nullable=False, index=True)
    user_feedback = Column(JSONB, nullable=True)  # User corrections and confirmations

    # Relationships
    photo = relationship("Photo", back_populates="detections")
    feedback = relationship(
        "UserFeedback", back_populates="detection", cascade="all, delete-orphan"
    )
    history = relationship(
        "DetectionHistory", back_populates="detection", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="check_confidence_range",
        ),
        CheckConstraint(
            "processing_time_ms > 0",
            name="check_processing_time_positive",
        ),
    )

    def __repr__(self):
        return f"<Detection(id={self.id}, type={self.detection_type}, confidence={self.confidence})>"
