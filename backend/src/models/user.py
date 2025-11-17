"""User model"""

from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.models.base import BaseModel


class User(BaseModel):
    """
    User model representing application users.
    Users belong to an organization and can have different roles.
    """

    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    role = Column(
        String(50), default="contractor", nullable=False
    )  # contractor, insurance_adjuster, project_manager
    organization_id = Column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Relationships
    organization = relationship("Organization", back_populates="users")
    photos = relationship("Photo", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
