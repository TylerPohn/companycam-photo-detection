"""Authentication endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from src.database import get_db
from src.models.user import User
from src.schemas.auth import LoginRequest, TokenResponse, RefreshTokenResponse, UserInfo
from src.services.auth_service import AuthService
from src.services.redis_service import RedisService
from src.api.errors import (
    unauthorized_error,
    validation_error,
    create_error_response
)
from src.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])
security = HTTPBearer()


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens

    - **email**: User email address
    - **password**: User password

    Returns access token and refresh token with user information
    """
    redis_service = RedisService()

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limiting (max 5 failed attempts per IP per 15 minutes)
    attempts = await redis_service.get_login_attempts(client_ip)
    if attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "type": "https://api.companycam.com/errors/rate_limit_exceeded",
                "title": "Too Many Requests",
                "status": 429,
                "detail": "Maximum login attempts exceeded. Please try again in 15 minutes.",
                "instance": request.url.path
            }
        )

    # Query user by email
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()

    # Verify user exists and password is correct
    if not user or not AuthService.verify_password(login_data.password, user.password_hash):
        # Increment failed login attempts
        await redis_service.increment_login_attempts(client_ip)

        # Return generic error message (don't reveal which field failed)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid email or password",
                "instance": request.url.path
            }
        )

    # Reset failed login attempts on success
    await redis_service.reset_login_attempts(client_ip)

    # Generate tokens
    access_token = AuthService.create_access_token(
        user_id=str(user.id),
        email=user.email,
        organization_id=str(user.organization_id),
        role=user.role
    )
    refresh_token = AuthService.create_refresh_token(user_id=str(user.id))

    # Calculate token expiration
    expires_in = settings.jwt_expiration_hours * 3600  # Convert to seconds

    # Return response with tokens and user info
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="Bearer",
        expires_in=expires_in,
        user=UserInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            organization_id=user.organization_id
        )
    )


@router.post("/refresh", response_model=RefreshTokenResponse, status_code=status.HTTP_200_OK)
async def refresh_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token

    - **Authorization**: Bearer {refresh_token}

    Returns new access token
    """
    token = credentials.credentials

    # Validate refresh token
    payload = AuthService.validate_token(token, token_type="refresh")

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Invalid or expired refresh token",
                "instance": request.url.path
            }
        )

    # Get user from database
    user_id = payload.get("sub")
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "User not found",
                "instance": request.url.path
            }
        )

    # Generate new access token
    access_token = AuthService.create_access_token(
        user_id=str(user.id),
        email=user.email,
        organization_id=str(user.organization_id),
        role=user.role
    )

    expires_in = settings.jwt_expiration_hours * 3600

    return RefreshTokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Logout user by blacklisting the access token

    - **Authorization**: Bearer {access_token}

    Returns 204 No Content on success
    """
    token = credentials.credentials

    # Validate token and get expiration
    payload = AuthService.decode_token(token)

    if not payload:
        # Even if token is invalid, return success (idempotent operation)
        return

    # Calculate time until token expiration
    exp = payload.get("exp")
    if exp:
        expiration_time = datetime.fromtimestamp(exp)
        now = datetime.utcnow()

        if expiration_time > now:
            # Calculate seconds until expiration
            seconds_until_expiration = int((expiration_time - now).total_seconds())

            # Add token to blacklist
            redis_service = RedisService()
            await redis_service.blacklist_token(token, seconds_until_expiration)

    return
