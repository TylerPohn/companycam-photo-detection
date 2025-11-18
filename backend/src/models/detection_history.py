"""Detection Result History model for tracking version changes"""

from sqlalchemy import Column, String, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class DetectionHistory(BaseModel):
    """
    Detection history model for tracking changes to detection results over time.
    Maintains a complete audit trail of detection updates.
    """

    __tablename__ = "detection_history"

    detection_id = Column(
        UUID(as_uuid=True),
        ForeignKey("detections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)  # Incremental version number
    detection_type = Column(String(50), nullable=False)
    model_version = Column(String(100), nullable=True)
    results = Column(JSONB, nullable=False)  # Snapshot of detection results
    confidence = Column(Float, nullable=True)
    change_reason = Column(String(255), nullable=True)  # Why the version was created
    changed_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    detection = relationship("Detection", back_populates="history")
    user = relationship("User")

    def __repr__(self):
        return f"<DetectionHistory(id={self.id}, detection_id={self.detection_id}, version={self.version})>"
