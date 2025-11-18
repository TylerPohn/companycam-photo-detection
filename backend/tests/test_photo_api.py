"""Integration tests for Photo Upload API"""

import pytest
import pytest_asyncio
from uuid import uuid4
from unittest.mock import patch, Mock
from jose import jwt
from datetime import datetime, timedelta

from src.config import settings
from src.models import User, Organization, Project, Photo, PhotoStatus


def create_jwt_token(user_id: str, expires_delta: timedelta = None) -> str:
    """Create a JWT token for testing"""
    if expires_delta is None:
        expires_delta = timedelta(hours=1)

    expire = datetime.utcnow() + expires_delta
    jwt_secret = settings.jwt_secret or settings.secret_key

    payload = {
        "sub": str(user_id),
        "exp": expire,
        "iat": datetime.utcnow(),
    }

    return jwt.encode(payload, jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers(sample_user):
    """Create authentication headers for testing"""
    token = create_jwt_token(sample_user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_s3_service():
    """Mock S3 service"""
    with patch("src.api.photos.S3Service") as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        # Mock validate_file to do nothing
        mock_instance.validate_file.return_value = None

        # Mock generate_s3_key
        mock_instance.generate_s3_key.return_value = "test-project/2025/11/17/test-photo.jpg"

        # Mock generate_presigned_upload_url
        mock_instance.generate_presigned_upload_url.return_value = {
            "upload_url": "https://s3.amazonaws.com/presigned-url",
            "s3_url": "https://s3.amazonaws.com/bucket/key.jpg",
            "s3_key": "test-project/2025/11/17/test-photo.jpg",
            "expires_in_seconds": 900,
            "headers": {"Content-Type": "image/jpeg"},
        }

        yield mock_instance


@pytest.fixture
def mock_queue_service():
    """Mock Queue service"""
    with patch("src.api.photos.QueueService") as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance

        # Mock publish method
        mock_instance.publish_photo_detection_message.return_value = True

        yield mock_instance


@pytest.mark.asyncio
class TestPhotoUploadUrlEndpoint:
    """Test POST /api/v1/photos/upload-url endpoint"""

    async def test_generate_upload_url_success(
        self,
        client,
        db_session,
        sample_user,
        sample_project,
        auth_headers,
        mock_s3_service,
    ):
        """Test successful upload URL generation"""
        # Override get_db dependency
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        request_data = {
            "project_id": str(sample_project.id),
            "file_name": "test_photo.jpg",
            "file_size": 1024 * 100,  # 100KB
            "mime_type": "image/jpeg",
        }

        response = client.post(
            "/api/v1/photos/upload-url",
            json=request_data,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "upload_id" in data
        assert "photo_id" in data
        assert "upload_url" in data
        assert "s3_url" in data
        assert "expires_in_seconds" in data
        assert data["expires_in_seconds"] == 900

        # Verify S3 service was called
        mock_s3_service.validate_file.assert_called_once()
        mock_s3_service.generate_presigned_upload_url.assert_called_once()

        # Clean up
        app.dependency_overrides.clear()

    async def test_generate_upload_url_unauthorized(
        self,
        client,
        db_session,
        sample_project,
    ):
        """Test upload URL generation without authentication"""
        request_data = {
            "project_id": str(sample_project.id),
            "file_name": "test_photo.jpg",
            "file_size": 1024 * 100,
            "mime_type": "image/jpeg",
        }

        response = client.post(
            "/api/v1/photos/upload-url",
            json=request_data,
        )

        assert response.status_code == 401

    async def test_generate_upload_url_project_not_found(
        self,
        client,
        db_session,
        auth_headers,
    ):
        """Test upload URL generation for non-existent project"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        request_data = {
            "project_id": str(uuid4()),  # Random UUID
            "file_name": "test_photo.jpg",
            "file_size": 1024 * 100,
            "mime_type": "image/jpeg",
        }

        response = client.post(
            "/api/v1/photos/upload-url",
            json=request_data,
            headers=auth_headers,
        )

        assert response.status_code == 404

        app.dependency_overrides.clear()

    async def test_generate_upload_url_invalid_mime_type(
        self,
        client,
        db_session,
        sample_project,
        auth_headers,
    ):
        """Test upload URL generation with invalid MIME type"""
        request_data = {
            "project_id": str(sample_project.id),
            "file_name": "test_photo.gif",
            "file_size": 1024 * 100,
            "mime_type": "image/gif",  # Not allowed
        }

        response = client.post(
            "/api/v1/photos/upload-url",
            json=request_data,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    async def test_generate_upload_url_file_too_large(
        self,
        client,
        db_session,
        sample_project,
        auth_headers,
    ):
        """Test upload URL generation with oversized file"""
        request_data = {
            "project_id": str(sample_project.id),
            "file_name": "huge_photo.jpg",
            "file_size": 51 * 1024 * 1024,  # 51MB - exceeds limit
            "mime_type": "image/jpeg",
        }

        response = client.post(
            "/api/v1/photos/upload-url",
            json=request_data,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestGetPhotoEndpoint:
    """Test GET /api/v1/photos/{photo_id} endpoint"""

    async def test_get_photo_success(
        self,
        client,
        db_session,
        sample_photo,
        auth_headers,
    ):
        """Test successful photo retrieval"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        response = client.get(
            f"/api/v1/photos/{sample_photo.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == str(sample_photo.id)
        assert data["s3_url"] == sample_photo.s3_url
        assert data["project_id"] == str(sample_photo.project_id)

        app.dependency_overrides.clear()

    async def test_get_photo_not_found(
        self,
        client,
        db_session,
        auth_headers,
    ):
        """Test photo retrieval for non-existent photo"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        response = client.get(
            f"/api/v1/photos/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404

        app.dependency_overrides.clear()

    async def test_get_photo_unauthorized(
        self,
        client,
        sample_photo,
    ):
        """Test photo retrieval without authentication"""
        response = client.get(f"/api/v1/photos/{sample_photo.id}")

        assert response.status_code == 401


@pytest.mark.asyncio
class TestUpdatePhotoStatusEndpoint:
    """Test PATCH /api/v1/photos/{photo_id}/status endpoint"""

    async def test_update_photo_status_success(
        self,
        client,
        db_session,
        sample_photo,
        auth_headers,
        mock_queue_service,
    ):
        """Test successful photo status update"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        response = client.patch(
            f"/api/v1/photos/{sample_photo.id}/status",
            json={"status": "uploaded"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should transition to processing when queue message is published
        assert data["status"] in ["uploaded", "processing"]

        app.dependency_overrides.clear()

    async def test_update_photo_status_invalid(
        self,
        client,
        db_session,
        sample_photo,
        auth_headers,
    ):
        """Test photo status update with invalid status"""
        response = client.patch(
            f"/api/v1/photos/{sample_photo.id}/status",
            json={"status": "invalid_status"},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
class TestDeletePhotoEndpoint:
    """Test DELETE /api/v1/photos/{photo_id} endpoint"""

    async def test_delete_photo_success(
        self,
        client,
        db_session,
        sample_user,
        sample_project,
        auth_headers,
    ):
        """Test successful photo deletion"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        # Create a photo to delete
        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/test.jpg",
            s3_key="test.jpg",
            status=PhotoStatus.UPLOADED,
        )
        db_session.add(photo)
        await db_session.commit()
        await db_session.refresh(photo)

        with patch("src.api.photos.S3Service") as mock_s3:
            mock_instance = Mock()
            mock_s3.return_value = mock_instance

            response = client.delete(
                f"/api/v1/photos/{photo.id}",
                headers=auth_headers,
            )

            assert response.status_code == 204

        app.dependency_overrides.clear()

    async def test_delete_photo_not_found(
        self,
        client,
        db_session,
        auth_headers,
    ):
        """Test deletion of non-existent photo"""
        from src.main import app
        from src.database import get_db

        async def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

        response = client.delete(
            f"/api/v1/photos/{uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404

        app.dependency_overrides.clear()
