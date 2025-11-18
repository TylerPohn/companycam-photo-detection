"""Authentication and authorization schemas"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import datetime
from uuid import UUID


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password (minimum 8 characters)")


class UserInfo(BaseModel):
    """User information in token response"""
    id: UUID = Field(..., description="User UUID")
    email: str = Field(..., description="User email")
    first_name: Optional[str] = Field(None, description="User first name")
    last_name: Optional[str] = Field(None, description="User last name")
    role: str = Field(..., description="User role")
    organization_id: UUID = Field(..., description="Organization UUID")

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserInfo = Field(..., description="User information")


class RefreshTokenResponse(BaseModel):
    """Refresh token response schema"""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="Bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")


class UserCreate(BaseModel):
    """User creation schema (for testing/admin purposes)"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    first_name: Optional[str] = Field(None, max_length=100, description="First name")
    last_name: Optional[str] = Field(None, max_length=100, description="Last name")
    role: str = Field(default="contractor", description="User role")
    organization_id: UUID = Field(..., description="Organization UUID")

    @validator("password")
    def validate_password(cls, v):
        """Validate password meets security requirements"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        # Additional validation can be added here (uppercase, lowercase, numbers, special chars)
        return v

    @validator("role")
    def validate_role(cls, v):
        """Validate role is valid"""
        valid_roles = ["contractor", "insurance_adjuster", "project_manager", "admin"]
        if v not in valid_roles:
            raise ValueError(f"Role must be one of: {', '.join(valid_roles)}")
        return v


class UserResponse(BaseModel):
    """User response schema"""
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    role: str
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
