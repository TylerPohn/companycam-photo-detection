"""Organization model"""

from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class Organization(BaseModel):
    """
    Organization model representing a company or entity.
    Used for multi-tenant data isolation.
    """

    __tablename__ = "organizations"

    name = Column(String(255), unique=True, nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="organization", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Organization(id={self.id}, name={self.name})>"
