"""Authentication service for JWT token management and password hashing"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from src.config import settings


class AuthService:
    """Service for handling authentication, JWT tokens, and password management"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt with salt rounds >= 12

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        # Convert password to bytes
        password_bytes = password.encode('utf-8')
        # Generate salt with 12 rounds
        salt = bcrypt.gensalt(rounds=12)
        # Hash password
        hashed = bcrypt.hashpw(password_bytes, salt)
        # Return as string
        return hashed.decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against its hash

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            True if password matches, False otherwise
        """
        # Convert to bytes
        password_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        # Verify
        return bcrypt.checkpw(password_bytes, hashed_bytes)

    @staticmethod
    def generate_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
        token_type: str = "access"
    ) -> str:
        """
        Generate a JWT token with the provided data

        Args:
            data: Dictionary of claims to include in the token
            expires_delta: Optional expiration time delta (defaults to 24 hours for access, 7 days for refresh)
            token_type: Type of token ('access' or 'refresh')

        Returns:
            Encoded JWT token string
        """
        to_encode = data.copy()

        # Set expiration
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            # Default expiration: 24 hours for access token, 7 days for refresh token
            hours = settings.jwt_expiration_hours if token_type == "access" else 168
            expire = datetime.utcnow() + timedelta(hours=hours)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "companycam-api",
            "type": token_type
        })

        # Use jwt_secret if available, otherwise fall back to secret_key
        secret = settings.jwt_secret or settings.secret_key
        encoded_jwt = jwt.encode(
            to_encode,
            secret,
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Decode and validate a JWT token

        Args:
            token: JWT token string to decode

        Returns:
            Dictionary of token claims if valid, None otherwise
        """
        try:
            secret = settings.jwt_secret or settings.secret_key
            payload = jwt.decode(
                token,
                secret,
                algorithms=[settings.jwt_algorithm]
            )
            return payload
        except JWTError:
            return None

    @staticmethod
    def validate_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token including signature, expiration, and type

        Args:
            token: JWT token string to validate
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Dictionary of token claims if valid, None otherwise
        """
        payload = AuthService.decode_token(token)

        if not payload:
            return None

        # Verify token type
        if payload.get("type") != token_type:
            return None

        # Check expiration (jose library already validates exp, but double-check)
        exp = payload.get("exp")
        if exp and datetime.fromtimestamp(exp) < datetime.utcnow():
            return None

        return payload

    @staticmethod
    def create_access_token(user_id: str, email: str, organization_id: str, role: str) -> str:
        """
        Create an access token for a user

        Args:
            user_id: User UUID
            email: User email
            organization_id: Organization UUID
            role: User role

        Returns:
            JWT access token
        """
        data = {
            "sub": user_id,
            "email": email,
            "organization_id": organization_id,
            "role": role
        }
        return AuthService.generate_token(data, token_type="access")

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        """
        Create a refresh token for a user

        Args:
            user_id: User UUID

        Returns:
            JWT refresh token
        """
        data = {"sub": user_id}
        return AuthService.generate_token(data, token_type="refresh")
