"""
Integration tests for database models.
"""

import pytest
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Organization, User, Project, Photo, Detection, Tag


class TestOrganizationModel:
    """Tests for Organization model"""

    @pytest.mark.asyncio
    async def test_create_organization(self, db_session: AsyncSession):
        """Test creating an organization"""
        org = Organization(name="ACME Corp")
        db_session.add(org)
        await db_session.commit()
        await db_session.refresh(org)

        assert org.id is not None
        assert org.name == "ACME Corp"
        assert org.created_at is not None
        assert org.updated_at is not None

    @pytest.mark.asyncio
    async def test_organization_unique_name(self, db_session: AsyncSession):
        """Test that organization names must be unique"""
        org1 = Organization(name="Unique Corp")
        db_session.add(org1)
        await db_session.commit()

        org2 = Organization(name="Unique Corp")
        db_session.add(org2)

        with pytest.raises(Exception):  # Should raise IntegrityError
            await db_session.commit()


class TestUserModel:
    """Tests for User model"""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession, sample_organization: Organization):
        """Test creating a user"""
        user = User(
            email="user@example.com",
            first_name="John",
            last_name="Doe",
            role="contractor",
            organization_id=sample_organization.id,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        assert user.id is not None
        assert user.email == "user@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.role == "contractor"
        assert user.organization_id == sample_organization.id

    @pytest.mark.asyncio
    async def test_user_organization_relationship(
        self, db_session: AsyncSession, sample_user: User, sample_organization: Organization
    ):
        """Test user-organization relationship"""
        await db_session.refresh(sample_user, ["organization"])
        assert sample_user.organization.id == sample_organization.id
        assert sample_user.organization.name == sample_organization.name


class TestProjectModel:
    """Tests for Project model"""

    @pytest.mark.asyncio
    async def test_create_project(self, db_session: AsyncSession, sample_organization: Organization):
        """Test creating a project"""
        project = Project(
            organization_id=sample_organization.id,
            name="Test Building",
            description="A test construction project",
            status="active",
        )
        db_session.add(project)
        await db_session.commit()
        await db_session.refresh(project)

        assert project.id is not None
        assert project.name == "Test Building"
        assert project.description == "A test construction project"
        assert project.status == "active"

    @pytest.mark.asyncio
    async def test_project_organization_relationship(
        self, db_session: AsyncSession, sample_project: Project, sample_organization: Organization
    ):
        """Test project-organization relationship"""
        await db_session.refresh(sample_project, ["organization"])
        assert sample_project.organization.id == sample_organization.id


class TestPhotoModel:
    """Tests for Photo model"""

    @pytest.mark.asyncio
    async def test_create_photo(
        self,
        db_session: AsyncSession,
        sample_user: User,
        sample_project: Project,
    ):
        """Test creating a photo"""
        photo = Photo(
            user_id=sample_user.id,
            project_id=sample_project.id,
            s3_url="https://s3.amazonaws.com/bucket/photo.jpg",
            s3_key="bucket/photo.jpg",
            file_size_bytes=2048000,
            mime_type="image/jpeg",
            width=4032,
            height=3024,
            exif_data={"camera": "iPhone 13", "gps": {"lat": 40.7128, "lon": -74.0060}},
        )
        db_session.add(photo)
        await db_session.commit()
        await db_session.refresh(photo)

        assert photo.id is not None
        assert photo.s3_url == "https://s3.amazonaws.com/bucket/photo.jpg"
        assert photo.s3_key == "bucket/photo.jpg"
        assert photo.file_size_bytes == 2048000
        assert photo.width == 4032
        assert photo.exif_data["camera"] == "iPhone 13"

    @pytest.mark.asyncio
    async def test_photo_relationships(
        self,
        db_session: AsyncSession,
        sample_photo: Photo,
        sample_user: User,
        sample_project: Project,
    ):
        """Test photo relationships with user and project"""
        await db_session.refresh(sample_photo, ["user", "project"])

        assert sample_photo.user.id == sample_user.id
        assert sample_photo.project.id == sample_project.id


class TestDetectionModel:
    """Tests for Detection model"""

    @pytest.mark.asyncio
    async def test_create_detection(self, db_session: AsyncSession, sample_photo: Photo):
        """Test creating a detection"""
        detection = Detection(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="yolov8-v1.0",
            results={
                "detections": [
                    {"class": "crack", "confidence": 0.95, "bbox": [100, 200, 300, 400]}
                ]
            },
            confidence=0.95,
            processing_time_ms=250,
            user_confirmed=False,
        )
        db_session.add(detection)
        await db_session.commit()
        await db_session.refresh(detection)

        assert detection.id is not None
        assert detection.detection_type == "damage"
        assert detection.confidence == 0.95
        assert detection.processing_time_ms == 250
        assert detection.user_confirmed is False

    @pytest.mark.asyncio
    async def test_detection_confidence_constraint(
        self, db_session: AsyncSession, sample_photo: Photo
    ):
        """Test that confidence must be between 0 and 1"""
        detection = Detection(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1.0",
            results={},
            confidence=1.5,  # Invalid: > 1
            processing_time_ms=100,
        )
        db_session.add(detection)

        with pytest.raises(Exception):  # Should raise CheckConstraint error
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_detection_cascade_delete(
        self, db_session: AsyncSession, sample_photo: Photo
    ):
        """Test that detections are deleted when photo is deleted"""
        detection = Detection(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1.0",
            results={},
            confidence=0.8,
            processing_time_ms=100,
        )
        db_session.add(detection)
        await db_session.commit()
        detection_id = detection.id

        # Delete the photo
        await db_session.delete(sample_photo)
        await db_session.commit()

        # Verify detection was also deleted
        result = await db_session.execute(
            select(Detection).where(Detection.id == detection_id)
        )
        assert result.scalar_one_or_none() is None


class TestTagModel:
    """Tests for Tag model"""

    @pytest.mark.asyncio
    async def test_create_tag_ai(self, db_session: AsyncSession, sample_photo: Photo):
        """Test creating an AI-generated tag"""
        tag = Tag(
            photo_id=sample_photo.id,
            tag="concrete",
            source="ai",
            confidence=0.92,
        )
        db_session.add(tag)
        await db_session.commit()
        await db_session.refresh(tag)

        assert tag.id is not None
        assert tag.tag == "concrete"
        assert tag.source == "ai"
        assert tag.confidence == 0.92

    @pytest.mark.asyncio
    async def test_create_tag_user(self, db_session: AsyncSession, sample_photo: Photo):
        """Test creating a user-generated tag"""
        tag = Tag(
            photo_id=sample_photo.id,
            tag="needs repair",
            source="user",
            confidence=None,
        )
        db_session.add(tag)
        await db_session.commit()
        await db_session.refresh(tag)

        assert tag.id is not None
        assert tag.tag == "needs repair"
        assert tag.source == "user"
        assert tag.confidence is None

    @pytest.mark.asyncio
    async def test_tag_source_constraint(self, db_session: AsyncSession, sample_photo: Photo):
        """Test that tag source must be 'ai' or 'user'"""
        tag = Tag(
            photo_id=sample_photo.id,
            tag="test",
            source="invalid",  # Invalid source
            confidence=None,
        )
        db_session.add(tag)

        with pytest.raises(Exception):  # Should raise CheckConstraint error
            await db_session.commit()

    @pytest.mark.asyncio
    async def test_tag_cascade_delete(self, db_session: AsyncSession, sample_photo: Photo):
        """Test that tags are deleted when photo is deleted"""
        tag = Tag(
            photo_id=sample_photo.id,
            tag="test tag",
            source="user",
        )
        db_session.add(tag)
        await db_session.commit()
        tag_id = tag.id

        # Delete the photo
        await db_session.delete(sample_photo)
        await db_session.commit()

        # Verify tag was also deleted
        result = await db_session.execute(select(Tag).where(Tag.id == tag_id))
        assert result.scalar_one_or_none() is None


class TestModelRelationships:
    """Tests for model relationships and complex queries"""

    @pytest.mark.asyncio
    async def test_organization_cascade_delete(
        self, db_session: AsyncSession, sample_organization: Organization, sample_user: User
    ):
        """Test that deleting an organization cascades to users and projects"""
        # Create additional data
        project = Project(
            organization_id=sample_organization.id,
            name="Test Project",
            status="active",
        )
        db_session.add(project)
        await db_session.commit()

        org_id = sample_organization.id

        # Delete organization
        await db_session.delete(sample_organization)
        await db_session.commit()

        # Verify users and projects were deleted
        users_result = await db_session.execute(
            select(User).where(User.organization_id == org_id)
        )
        assert len(users_result.scalars().all()) == 0

        projects_result = await db_session.execute(
            select(Project).where(Project.organization_id == org_id)
        )
        assert len(projects_result.scalars().all()) == 0

    @pytest.mark.asyncio
    async def test_photo_with_multiple_detections(
        self, db_session: AsyncSession, sample_photo: Photo
    ):
        """Test that a photo can have multiple detections"""
        detection1 = Detection(
            photo_id=sample_photo.id,
            detection_type="damage",
            model_version="v1.0",
            results={},
            confidence=0.9,
            processing_time_ms=100,
        )
        detection2 = Detection(
            photo_id=sample_photo.id,
            detection_type="material",
            model_version="v1.0",
            results={},
            confidence=0.85,
            processing_time_ms=150,
        )
        db_session.add_all([detection1, detection2])
        await db_session.commit()

        await db_session.refresh(sample_photo, ["detections"])
        assert len(sample_photo.detections) == 2

    @pytest.mark.asyncio
    async def test_photo_with_multiple_tags(
        self, db_session: AsyncSession, sample_photo: Photo
    ):
        """Test that a photo can have multiple tags"""
        tag1 = Tag(photo_id=sample_photo.id, tag="concrete", source="ai", confidence=0.9)
        tag2 = Tag(photo_id=sample_photo.id, tag="damaged", source="ai", confidence=0.8)
        tag3 = Tag(photo_id=sample_photo.id, tag="urgent", source="user")

        db_session.add_all([tag1, tag2, tag3])
        await db_session.commit()

        await db_session.refresh(sample_photo, ["tags"])
        assert len(sample_photo.tags) == 3
