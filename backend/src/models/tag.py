"""Tag model"""

from sqlalchemy import Column, String, Float, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Tag(BaseModel):
    """
    Tag model representing labels/tags applied to photos.
    Tags can be AI-generated or user-generated.
    """

    __tablename__ = "tags"

    photo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("photos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag = Column(String(100), nullable=False, index=True)
    source = Column(String(20), default="ai", nullable=False)  # ai, user
    confidence = Column(
        Float, nullable=True
    )  # NULL if user-generated, confidence if AI

    # Relationships
    photo = relationship("Photo", back_populates="tags")

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="check_tag_confidence_range",
        ),
        CheckConstraint(
            "source IN ('ai', 'user')",
            name="check_tag_source",
        ),
    )

    def __repr__(self):
        return f"<Tag(id={self.id}, tag={self.tag}, source={self.source})>"
