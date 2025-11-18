"""Tests for health check endpoints"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.database import get_db


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
class TestBasicHealthCheck:
    """Test basic health check endpoint"""

    async def test_basic_health_check(self, async_client: AsyncClient):
        """Test GET /health endpoint"""
        response = await async_client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data

    async def test_basic_health_no_auth_required(self, async_client: AsyncClient):
        """Test that /health doesn't require authentication"""
        response = await async_client.get("/health")

        # Should succeed without auth
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
class TestDetailedHealthCheck:
    """Test detailed health check endpoint"""

    async def test_detailed_health_check(self, async_client: AsyncClient):
        """Test GET /api/v1/health endpoint"""
        response = await async_client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "services" in data

        # Check services structure
        services = data["services"]
        assert "database" in services
        assert "redis" in services
        assert "s3" in services

    async def test_detailed_health_no_auth_required(self, async_client: AsyncClient):
        """Test that /api/v1/health doesn't require authentication"""
        response = await async_client.get("/api/v1/health")

        # Should succeed without auth
        assert response.status_code == status.HTTP_200_OK

    async def test_detailed_health_version(self, async_client: AsyncClient):
        """Test that health check returns version"""
        response = await async_client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["version"] == "1.0.0"

    async def test_detailed_health_database_connected(
        self, async_client: AsyncClient
    ):
        """Test that database service status is included"""
        response = await async_client.get("/api/v1/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Database service status should be included (may be connected or disconnected based on config)
        assert "database" in data["services"]
        assert isinstance(data["services"]["database"], str)
