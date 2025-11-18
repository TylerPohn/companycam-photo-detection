"""API dependencies for authentication and authorization"""

from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from src.database import get_db
from src.models import User
from src.services.auth_service import AuthService
from src.services.redis_service import RedisService


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        User object

    Raises:
        HTTPException: If token is invalid or user not found
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Authorization header missing"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid authorization header format"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]

    # Check if token is blacklisted
    redis_service = RedisService()
    if await redis_service.is_token_blacklisted(token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Token has been revoked"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate token using AuthService
    payload = AuthService.validate_token(token, token_type="access")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid or expired token"
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: Optional[str] = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid token payload"
            },
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid user ID in token"
            },
        )

    # Get user from database
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "User not found"
            },
        )

    return user


async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.

    Args:
        authorization: Authorization header with Bearer token
        db: Database session

    Returns:
        User object or None
    """
    if not authorization:
        return None

    try:
        return await get_current_user(authorization, db)
    except HTTPException:
        return None
