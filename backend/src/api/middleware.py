"""Authentication and authorization middleware"""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.services.auth_service import AuthService
from src.services.redis_service import RedisService

security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Middleware for JWT token authentication and authorization"""

    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = [
        "/",
        "/health",
        "/api/v1/health",
        "/api/v1/auth/login",
        "/docs",
        "/redoc",
        "/openapi.json"
    ]

    @staticmethod
    async def get_current_user(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = None):
        """
        Extract and validate JWT token from Authorization header

        Args:
            request: FastAPI request object
            credentials: HTTP authorization credentials

        Returns:
            Dictionary containing user information from token

        Raises:
            HTTPException: 401 if token is missing or invalid, 403 if token is expired or blacklisted
        """
        # Check if endpoint is public
        if request.url.path in AuthMiddleware.PUBLIC_ENDPOINTS:
            return None

        # Extract token
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "type": "https://api.companycam.com/errors/unauthorized",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Missing authentication credentials",
                    "instance": request.url.path
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = credentials.credentials

        # Check if token is blacklisted (logged out)
        redis_service = RedisService()
        if await redis_service.is_token_blacklisted(token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "type": "https://api.companycam.com/errors/unauthorized",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Token has been revoked",
                    "instance": request.url.path
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token
        payload = AuthService.validate_token(token, token_type="access")

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "type": "https://api.companycam.com/errors/unauthorized",
                    "title": "Unauthorized",
                    "status": 401,
                    "detail": "Invalid or expired token",
                    "instance": request.url.path
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Return user context
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "organization_id": payload.get("organization_id"),
            "role": payload.get("role")
        }

    @staticmethod
    def require_role(*allowed_roles: str) -> Callable:
        """
        Decorator factory to require specific roles for endpoint access

        Args:
            allowed_roles: Roles that are allowed to access the endpoint

        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            async def wrapper(*args, current_user: dict = None, **kwargs):
                if not current_user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail={
                            "type": "https://api.companycam.com/errors/unauthorized",
                            "title": "Unauthorized",
                            "status": 401,
                            "detail": "Authentication required"
                        }
                    )

                user_role = current_user.get("role")
                if user_role not in allowed_roles:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail={
                            "type": "https://api.companycam.com/errors/forbidden",
                            "title": "Forbidden",
                            "status": 403,
                            "detail": f"Role '{user_role}' does not have permission to access this resource"
                        }
                    )

                return await func(*args, current_user=current_user, **kwargs)

            return wrapper
        return decorator
