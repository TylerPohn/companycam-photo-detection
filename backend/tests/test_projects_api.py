"""Tests for project API endpoints"""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from src.main import app
from src.database import get_db
from src.models import User, Organization, Project
from src.services.auth_service import AuthService


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession):
    """Create async test client with database override"""

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(sample_user: User):
    """Create authentication headers for test user"""
    token = AuthService.create_access_token(
        user_id=str(sample_user.id),
        email=sample_user.email,
        organization_id=str(sample_user.organization_id),
        role=sample_user.role
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestGetProjects:
    """Test GET /api/v1/projects endpoint"""

    async def test_get_projects_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test getting projects list"""
        response = await async_client.get(
            "/api/v1/projects",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "projects" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert data["total"] >= 1
        assert len(data["projects"]) >= 1

        # Check project structure
        project = data["projects"][0]
        assert "id" in project
        assert "name" in project
        assert "status" in project
        assert "created_at" in project

    async def test_get_projects_pagination(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test projects pagination"""
        response = await async_client.get(
            "/api/v1/projects?page=1&page_size=10",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["page"] == 1
        assert data["page_size"] == 10

    async def test_get_projects_unauthorized(
        self, async_client: AsyncClient
    ):
        """Test getting projects without authentication"""
        response = await async_client.get("/api/v1/projects")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_projects_different_org_filtered(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        sample_user: User
    ):
        """Test that projects from different organization are not returned"""
        # Create another organization and project
        other_org = Organization(name="Other Organization")
        db_session.add(other_org)
        await db_session.commit()
        await db_session.refresh(other_org)

        other_project = Project(
            organization_id=other_org.id,
            name="Other Project",
            status="active"
        )
        db_session.add(other_project)
        await db_session.commit()

        # Get auth headers for sample user
        token = AuthService.create_access_token(
            user_id=str(sample_user.id),
            email=sample_user.email,
            organization_id=str(sample_user.organization_id),
            role=sample_user.role
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await async_client.get(
            "/api/v1/projects",
            headers=headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should not see other organization's project
        project_ids = [p["id"] for p in data["projects"]]
        assert str(other_project.id) not in project_ids


@pytest.mark.asyncio
class TestGetProjectDetails:
    """Test GET /api/v1/projects/{project_id} endpoint"""

    async def test_get_project_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test getting project details"""
        response = await async_client.get(
            f"/api/v1/projects/{sample_project.id}",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["id"] == str(sample_project.id)
        assert data["name"] == sample_project.name
        assert data["status"] == sample_project.status
        assert "photo_count" in data
        assert "last_photo_at" in data

    async def test_get_project_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test getting non-existent project"""
        fake_id = "12345678-1234-1234-1234-123456789012"
        response = await async_client.get(
            f"/api/v1/projects/{fake_id}",
            headers=auth_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_get_project_unauthorized(
        self,
        async_client: AsyncClient,
        sample_project: Project
    ):
        """Test getting project without authentication"""
        response = await async_client.get(
            f"/api/v1/projects/{sample_project.id}"
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_project_different_org_denied(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        sample_user: User
    ):
        """Test that accessing project from different organization is denied"""
        # Create another organization and project
        other_org = Organization(name="Other Organization")
        db_session.add(other_org)
        await db_session.commit()
        await db_session.refresh(other_org)

        other_project = Project(
            organization_id=other_org.id,
            name="Other Project",
            status="active"
        )
        db_session.add(other_project)
        await db_session.commit()

        # Try to access with sample user's token
        token = AuthService.create_access_token(
            user_id=str(sample_user.id),
            email=sample_user.email,
            organization_id=str(sample_user.organization_id),
            role=sample_user.role
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await async_client.get(
            f"/api/v1/projects/{other_project.id}",
            headers=headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
class TestUpdateProject:
    """Test PATCH /api/v1/projects/{project_id} endpoint"""

    async def test_update_project_name(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test updating project name"""
        response = await async_client.patch(
            f"/api/v1/projects/{sample_project.id}",
            headers=auth_headers,
            json={"name": "Updated Project Name"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == "Updated Project Name"
        assert data["id"] == str(sample_project.id)

    async def test_update_project_description(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test updating project description"""
        response = await async_client.patch(
            f"/api/v1/projects/{sample_project.id}",
            headers=auth_headers,
            json={"description": "New description"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["description"] == "New description"

    async def test_update_project_status(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test updating project status"""
        response = await async_client.patch(
            f"/api/v1/projects/{sample_project.id}",
            headers=auth_headers,
            json={"status": "completed"}
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["status"] == "completed"

    async def test_update_project_multiple_fields(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        sample_project: Project
    ):
        """Test updating multiple project fields"""
        response = await async_client.patch(
            f"/api/v1/projects/{sample_project.id}",
            headers=auth_headers,
            json={
                "name": "Multi-Update Project",
                "description": "Updated description",
                "status": "archived"
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["name"] == "Multi-Update Project"
        assert data["description"] == "Updated description"
        assert data["status"] == "archived"

    async def test_update_project_not_found(
        self,
        async_client: AsyncClient,
        auth_headers: dict
    ):
        """Test updating non-existent project"""
        fake_id = "12345678-1234-1234-1234-123456789012"
        response = await async_client.patch(
            f"/api/v1/projects/{fake_id}",
            headers=auth_headers,
            json={"name": "New Name"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_project_unauthorized(
        self,
        async_client: AsyncClient,
        sample_project: Project
    ):
        """Test updating project without authentication"""
        response = await async_client.patch(
            f"/api/v1/projects/{sample_project.id}",
            json={"name": "New Name"}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_update_project_different_org_forbidden(
        self,
        async_client: AsyncClient,
        db_session: AsyncSession,
        sample_user: User
    ):
        """Test that updating project from different organization is forbidden"""
        # Create another organization and project
        other_org = Organization(name="Other Organization")
        db_session.add(other_org)
        await db_session.commit()
        await db_session.refresh(other_org)

        other_project = Project(
            organization_id=other_org.id,
            name="Other Project",
            status="active"
        )
        db_session.add(other_project)
        await db_session.commit()

        # Try to update with sample user's token
        token = AuthService.create_access_token(
            user_id=str(sample_user.id),
            email=sample_user.email,
            organization_id=str(sample_user.organization_id),
            role=sample_user.role
        )
        headers = {"Authorization": f"Bearer {token}"}

        response = await async_client.patch(
            f"/api/v1/projects/{other_project.id}",
            headers=headers,
            json={"name": "Hacked Name"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
