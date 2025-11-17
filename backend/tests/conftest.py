"""Pytest configuration and shared fixtures"""

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.main import app
from src.database import Base
from src.models import Organization, User, Project, Photo, Detection, Tag


# Test database URL (use a separate test database)
TEST_DATABASE_URL = "postgresql+asyncpg://companycam:dev_password@localhost:5432/companycam_detection_test"


@pytest.fixture
def client():
    """FastAPI test client fixture"""
    return TestClient(app)


@pytest.fixture
def test_data():
    """Sample test data fixture"""
    return {
        "test_user": {"username": "testuser", "email": "test@example.com"},
        "test_photo": {"filename": "test.jpg", "size": 1024},
    }


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create a test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a database session for testing"""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def sample_organization(db_session: AsyncSession) -> Organization:
    """Create a sample organization for testing"""
    org = Organization(name="Test Organization")
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def sample_user(db_session: AsyncSession, sample_organization: Organization) -> User:
    """Create a sample user for testing"""
    user = User(
        email="test@example.com",
        first_name="Test",
        last_name="User",
        role="contractor",
        organization_id=sample_organization.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def sample_project(db_session: AsyncSession, sample_organization: Organization) -> Project:
    """Create a sample project for testing"""
    project = Project(
        organization_id=sample_organization.id,
        name="Test Project",
        description="A test project",
        status="active",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest_asyncio.fixture
async def sample_photo(
    db_session: AsyncSession,
    sample_user: User,
    sample_project: Project,
) -> Photo:
    """Create a sample photo for testing"""
    photo = Photo(
        user_id=sample_user.id,
        project_id=sample_project.id,
        s3_url="https://s3.amazonaws.com/test/photo.jpg",
        s3_key="test/photo.jpg",
        file_size_bytes=1024000,
        mime_type="image/jpeg",
        width=1920,
        height=1080,
        exif_data={"camera": "Test Camera"},
    )
    db_session.add(photo)
    await db_session.commit()
    await db_session.refresh(photo)
    return photo
