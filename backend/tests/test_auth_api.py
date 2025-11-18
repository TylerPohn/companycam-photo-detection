"""Tests for authentication API endpoints"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.database import get_db
from src.models import User, Organization
from src.services.auth_service import AuthService
from src.services.redis_service import RedisService


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """Create async test client with database override"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.mark.asyncio
class TestLoginEndpoint:
    """Test login endpoint functionality"""

    async def test_login_success(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test successful login with valid credentials"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 86400  # 24 hours
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["role"] == "contractor"

    async def test_login_invalid_email(self, async_client: AsyncClient):
        """Test login with non-existent email"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePassword123!"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["status"] == 401
        assert "invalid email or password" in data["detail"].lower()

    async def test_login_invalid_password(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test login with incorrect password"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "WrongPassword123!"
            }
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        data = response.json()
        assert data["status"] == 401

    async def test_login_missing_email(self, async_client: AsyncClient):
        """Test login with missing email field"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"password": "TestPassword123!"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_login_missing_password(self, async_client: AsyncClient):
        """Test login with missing password field"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com"}
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_login_invalid_email_format(self, async_client: AsyncClient):
        """Test login with invalid email format"""
        response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "not-an-email",
                "password": "TestPassword123!"
            }
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
class TestTokenRefreshEndpoint:
    """Test token refresh endpoint functionality"""

    async def test_refresh_token_success(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test successful token refresh"""
        # First, login to get refresh token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Now refresh the token
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {refresh_token}"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "access_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 86400

    async def test_refresh_with_access_token_fails(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test that using access token for refresh fails"""
        # Login to get access token
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Try to refresh with access token (should fail)
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_without_token(self, async_client: AsyncClient):
        """Test refresh without authorization header"""
        response = await async_client.post("/api/v1/auth/refresh")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_refresh_with_invalid_token(self, async_client: AsyncClient):
        """Test refresh with invalid token"""
        response = await async_client.post(
            "/api/v1/auth/refresh",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
class TestLogoutEndpoint:
    """Test logout endpoint functionality"""

    async def test_logout_success(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test successful logout"""
        # Login first
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Logout
        response = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify token is blacklisted
        redis_service = RedisService()
        is_blacklisted = await redis_service.is_token_blacklisted(access_token)
        assert is_blacklisted is True

    async def test_logout_without_token(self, async_client: AsyncClient):
        """Test logout without authorization header"""
        response = await async_client.post("/api/v1/auth/logout")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    async def test_logout_idempotent(
        self, async_client: AsyncClient, sample_user: User
    ):
        """Test that logout is idempotent (can be called multiple times)"""
        # Login first
        login_response = await async_client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "TestPassword123!"
            }
        )
        access_token = login_response.json()["access_token"]

        # Logout twice
        response1 = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response2 = await async_client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        # Both should succeed
        assert response1.status_code == status.HTTP_204_NO_CONTENT
        assert response2.status_code == status.HTTP_204_NO_CONTENT
