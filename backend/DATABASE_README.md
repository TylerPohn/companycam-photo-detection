# Database Setup and Usage Guide

This document provides comprehensive information about the database schema, models, migrations, and usage for the CompanyCam Photo Detection backend.

## Table of Contents

- [Overview](#overview)
- [Database Schema](#database-schema)
- [Setup Instructions](#setup-instructions)
- [Running Migrations](#running-migrations)
- [Seeding Data](#seeding-data)
- [Row-Level Security](#row-level-security)
- [Testing](#testing)

## Overview

The application uses **PostgreSQL 15+** as the database with:
- **SQLAlchemy 2.0** as the ORM
- **Alembic** for database migrations
- **asyncpg** for async database operations
- **UUID** for primary keys
- **JSONB** for flexible metadata storage

## Database Schema

### Tables

#### 1. Organizations
Multi-tenant isolation - each organization represents a company or entity.

```sql
- id: UUID (PK)
- name: VARCHAR(255) UNIQUE
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 2. Users
Application users belonging to organizations.

```sql
- id: UUID (PK)
- email: VARCHAR(255) UNIQUE
- first_name: VARCHAR(100)
- last_name: VARCHAR(100)
- role: VARCHAR(50) (contractor, insurance_adjuster, project_manager)
- organization_id: UUID (FK -> organizations.id)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 3. Projects
Construction projects or job sites.

```sql
- id: UUID (PK)
- organization_id: UUID (FK -> organizations.id)
- name: VARCHAR(255)
- description: TEXT
- status: VARCHAR(50) (active, completed, archived)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 4. Photos
Uploaded construction photos.

```sql
- id: UUID (PK)
- user_id: UUID (FK -> users.id)
- project_id: UUID (FK -> projects.id)
- s3_url: TEXT
- s3_key: VARCHAR(500) UNIQUE
- file_size_bytes: INTEGER
- mime_type: VARCHAR(50)
- width: INTEGER
- height: INTEGER
- exif_data: JSONB
- uploaded_at: TIMESTAMP
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 5. Detections
AI detection results for photos.

```sql
- id: UUID (PK)
- photo_id: UUID (FK -> photos.id, ON DELETE CASCADE)
- detection_type: VARCHAR(50) (damage, material, volume)
- model_version: VARCHAR(100)
- results: JSONB
- confidence: FLOAT (0-1)
- processing_time_ms: INTEGER
- user_confirmed: BOOLEAN
- user_feedback: JSONB
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

#### 6. Tags
Labels applied to photos (AI or user-generated).

```sql
- id: UUID (PK)
- photo_id: UUID (FK -> photos.id, ON DELETE CASCADE)
- tag: VARCHAR(100)
- source: VARCHAR(20) (ai, user)
- confidence: FLOAT (0-1, nullable)
- created_at: TIMESTAMP
- updated_at: TIMESTAMP
```

### Indexes

Performance-optimized indexes:
- `photos(user_id)` - Filter photos by user
- `photos(project_id)` - Filter photos by project
- `photos(created_at)` - Time-based queries
- `detections(photo_id)` - Get detections for photo
- `detections(detection_type)` - Filter by detection type
- `detections(created_at)` - Time-based queries
- `detections(user_confirmed)` - Find unconfirmed detections
- `tags(photo_id)` - Get tags for photo
- `tags(tag)` - Search by tag name

### Relationships

```
Organization (1) -> (many) Users
Organization (1) -> (many) Projects
User (1) -> (many) Photos
Project (1) -> (many) Photos
Photo (1) -> (many) Detections (CASCADE DELETE)
Photo (1) -> (many) Tags (CASCADE DELETE)
```

## Setup Instructions

### 1. Install PostgreSQL

#### Using Docker (Recommended)
```bash
docker-compose up -d postgres
```

#### Using Local PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql-15

# macOS
brew install postgresql@15
```

### 2. Create Database

The database is automatically created by Docker Compose. For manual setup:

```bash
psql -U postgres
CREATE DATABASE companycam_detection;
CREATE USER companycam WITH PASSWORD 'dev_password';
GRANT ALL PRIVILEGES ON DATABASE companycam_detection TO companycam;
```

### 3. Set Environment Variables

Copy `.env.example` to `.env` and update:

```bash
DATABASE_URL=postgresql://companycam:dev_password@localhost:5432/companycam_detection
```

### 4. Initialize Database Extensions

```bash
psql -U companycam -d companycam_detection -f backend/config/init.sql
```

## Running Migrations

### Create Initial Migration

Already created in `alembic/versions/`. To create new migrations:

```bash
cd backend
source venv/bin/activate

# Auto-generate migration from model changes
alembic revision --autogenerate -m "Description of changes"

# Or create empty migration
alembic revision -m "Description"
```

### Apply Migrations

```bash
cd backend
source venv/bin/activate

# Upgrade to latest
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Downgrade one version
alembic downgrade -1

# View current version
alembic current

# View migration history
alembic history
```

### Test Migration

```bash
# Test forward and backward migration
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

## Seeding Data

### Run Seed Script

```bash
cd backend
source venv/bin/activate
python scripts/seed_data.py
```

This creates:
- 2 organizations
- 3 users
- 3 projects
- 3 photos
- 3 detections
- 6 tags

### Custom Seeding

Create your own seed script in `backend/scripts/`:

```python
from src.models import Organization, User, Project
from src.database import AsyncSessionLocal

async def seed_custom_data():
    async with AsyncSessionLocal() as session:
        org = Organization(name="My Company")
        session.add(org)
        await session.commit()
```

## Row-Level Security

### Enable RLS Policies

```bash
psql -U companycam -d companycam_detection -f backend/config/rls-policies.sql
```

### Using RLS in Application

Set the organization context for each request:

```python
from sqlalchemy import text

async def get_data_for_org(db: AsyncSession, org_id: UUID):
    # Set organization context
    await db.execute(
        text("SET LOCAL app.current_organization_id = :org_id"),
        {"org_id": str(org_id)}
    )

    # All subsequent queries are filtered by organization
    photos = await db.execute(select(Photo))
    return photos.scalars().all()
```

## Testing

### Run All Tests

```bash
cd backend
source venv/bin/activate
pytest tests/ -v
```

### Run Specific Tests

```bash
# Test models only
pytest tests/test_models.py -v

# Test a specific class
pytest tests/test_models.py::TestPhotoModel -v

# Test a specific test
pytest tests/test_models.py::TestPhotoModel::test_create_photo -v
```

### Test Coverage

```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### Test Database

Tests use a separate database `companycam_detection_test`. Create it:

```bash
psql -U postgres -c "CREATE DATABASE companycam_detection_test;"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE companycam_detection_test TO companycam;"
```

## Model Usage Examples

### Creating Records

```python
from src.models import Organization, User, Photo
from src.database import AsyncSessionLocal

async def create_photo():
    async with AsyncSessionLocal() as session:
        # Create organization
        org = Organization(name="ACME Corp")
        session.add(org)
        await session.flush()

        # Create user
        user = User(
            email="user@acme.com",
            first_name="John",
            last_name="Doe",
            role="contractor",
            organization_id=org.id
        )
        session.add(user)
        await session.flush()

        # Create photo
        photo = Photo(
            user_id=user.id,
            project_id=project_id,
            s3_url="https://...",
            s3_key="photos/photo.jpg",
            file_size_bytes=2048000,
            mime_type="image/jpeg"
        )
        session.add(photo)
        await session.commit()
```

### Querying with Relationships

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Load photo with relationships
result = await session.execute(
    select(Photo)
    .options(
        selectinload(Photo.user),
        selectinload(Photo.detections),
        selectinload(Photo.tags)
    )
    .where(Photo.id == photo_id)
)
photo = result.scalar_one()

# Access relationships
print(photo.user.email)
print(len(photo.detections))
for tag in photo.tags:
    print(tag.tag)
```

## Troubleshooting

### Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Check connection
psql -U companycam -d companycam_detection -c "SELECT 1;"
```

### Migration Issues

```bash
# Reset migrations (DESTRUCTIVE - loses all data)
alembic downgrade base
alembic upgrade head

# Or drop and recreate database
dropdb companycam_detection
createdb companycam_detection
alembic upgrade head
```

### Test Database Issues

```bash
# Drop and recreate test database
dropdb companycam_detection_test
createdb companycam_detection_test
```

## Additional Resources

- [SQLAlchemy 2.0 Documentation](https://docs.sqlalchemy.org/en/20/)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [asyncpg Documentation](https://magicstack.github.io/asyncpg/)
