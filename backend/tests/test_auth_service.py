"""Tests for authentication service"""

import pytest
from datetime import datetime, timedelta
from src.services.auth_service import AuthService


class TestPasswordHashing:
    """Test password hashing and verification"""

    def test_hash_password(self):
        """Test password hashing generates a hash"""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert hashed is not None
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt prefix

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "TestPassword123!"
        hashed = AuthService.hash_password(password)

        assert AuthService.verify_password("WrongPassword", hashed) is False

    def test_hash_same_password_different_hashes(self):
        """Test that hashing the same password twice produces different hashes (due to salt)"""
        password = "TestPassword123!"
        hash1 = AuthService.hash_password(password)
        hash2 = AuthService.hash_password(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert AuthService.verify_password(password, hash1) is True
        assert AuthService.verify_password(password, hash2) is True


class TestJWTTokens:
    """Test JWT token generation and validation"""

    def test_generate_access_token(self):
        """Test access token generation"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        email = "test@example.com"
        org_id = "223e4567-e89b-12d3-a456-426614174000"
        role = "contractor"

        token = AuthService.create_access_token(user_id, email, org_id, role)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_refresh_token(self):
        """Test refresh token generation"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = AuthService.create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_valid_token(self):
        """Test decoding a valid token"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        email = "test@example.com"
        org_id = "223e4567-e89b-12d3-a456-426614174000"
        role = "contractor"

        token = AuthService.create_access_token(user_id, email, org_id, role)
        payload = AuthService.decode_token(token)

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["organization_id"] == org_id
        assert payload["role"] == role
        assert payload["type"] == "access"
        assert payload["iss"] == "companycam-api"

    def test_decode_invalid_token(self):
        """Test decoding an invalid token"""
        payload = AuthService.decode_token("invalid.token.here")

        assert payload is None

    def test_validate_access_token(self):
        """Test validating an access token"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        email = "test@example.com"
        org_id = "223e4567-e89b-12d3-a456-426614174000"
        role = "contractor"

        token = AuthService.create_access_token(user_id, email, org_id, role)
        payload = AuthService.validate_token(token, token_type="access")

        assert payload is not None
        assert payload["sub"] == user_id

    def test_validate_refresh_token(self):
        """Test validating a refresh token"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = AuthService.create_refresh_token(user_id)
        payload = AuthService.validate_token(token, token_type="refresh")

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["type"] == "refresh"

    def test_validate_wrong_token_type(self):
        """Test that validating with wrong token type fails"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        access_token = AuthService.create_access_token(
            user_id, "test@example.com", "org_id", "contractor"
        )

        # Try to validate access token as refresh token
        payload = AuthService.validate_token(access_token, token_type="refresh")

        assert payload is None

    def test_token_contains_expiration(self):
        """Test that token contains expiration claim"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = AuthService.create_access_token(
            user_id, "test@example.com", "org_id", "contractor"
        )
        payload = AuthService.decode_token(token)

        assert payload is not None
        assert "exp" in payload
        assert "iat" in payload

        # Verify expiration is in the future
        exp_time = datetime.fromtimestamp(payload["exp"])
        assert exp_time > datetime.utcnow()

    def test_custom_expiration(self):
        """Test token generation with custom expiration"""
        data = {"sub": "test_user"}
        expires_delta = timedelta(minutes=5)

        token = AuthService.generate_token(data, expires_delta=expires_delta)
        payload = AuthService.decode_token(token)

        assert payload is not None
        exp_time = datetime.fromtimestamp(payload["exp"])
        iat_time = datetime.fromtimestamp(payload["iat"])

        # Expiration should be approximately 5 minutes from issued time
        time_diff = (exp_time - iat_time).total_seconds()
        assert 295 <= time_diff <= 305  # Allow 5 second tolerance
