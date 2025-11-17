"""Project model"""

from sqlalchemy import Column, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Project(BaseModel):
    """
    Project model representing a construction project or job site.
    Projects belong to an organization and contain photos.
    """

    __tablename__ = "projects"

    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(50), default="active", nullable=False
    )  # active, completed, archived

    # Relationships
    organization = relationship("Organization", back_populates="projects")
    photos = relationship("Photo", back_populates="project", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"
