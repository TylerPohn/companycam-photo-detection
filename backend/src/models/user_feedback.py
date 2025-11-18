"""User Feedback model for detection confirmations and corrections"""

from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class UserFeedback(BaseModel):
    """
    User feedback model for storing user confirmations and corrections
    on detection results. Used to improve model accuracy over time.
    """

    __tablename__ = "user_feedback"

    detection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("detections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feedback_type = Column(
        String(50), nullable=False, index=True
    )  # confirmed, rejected, corrected
    corrections = Column(
        JSONB, nullable=True
    )  # Corrected values (e.g., adjusted counts, damage type)
    comments = Column(Text, nullable=True)  # User comments/notes

    # Relationships
    detection = relationship("Detection", back_populates="feedback")
    user = relationship("User")

    def __repr__(self):
        return f"<UserFeedback(id={self.id}, detection_id={self.detection_id}, type={self.feedback_type})>"
