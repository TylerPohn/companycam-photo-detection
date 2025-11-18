#!/usr/bin/env python3
"""
Database seeding script for development and testing.
Creates sample organizations, users, projects, photos, detections, and tags.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

# Add parent directory to path to import our modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession
from src.database import async_engine, Base, AsyncSessionLocal
from src.models import Organization, User, Project, Photo, Detection, Tag


async def create_tables():
    """Create all database tables"""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")


async def seed_data():
    """Seed the database with sample data"""
    async with AsyncSessionLocal() as session:
        try:
            # Create organizations
            org1 = Organization(
                name="ACME Construction Co."
            )
            org2 = Organization(
                name="BuildRight Contractors"
            )
            session.add_all([org1, org2])
            await session.flush()
            print("✓ Created organizations")

            # Create users
            user1 = User(
                email="john.doe@acme.com",
                first_name="John",
                last_name="Doe",
                role="contractor",
                organization_id=org1.id,
            )
            user2 = User(
                email="jane.smith@acme.com",
                first_name="Jane",
                last_name="Smith",
                role="project_manager",
                organization_id=org1.id,
            )
            user3 = User(
                email="bob.wilson@buildright.com",
                first_name="Bob",
                last_name="Wilson",
                role="insurance_adjuster",
                organization_id=org2.id,
            )
            session.add_all([user1, user2, user3])
            await session.flush()
            print("✓ Created users")

            # Create projects
            project1 = Project(
                organization_id=org1.id,
                name="Downtown Office Renovation",
                description="Complete renovation of 5-story office building",
                status="active",
            )
            project2 = Project(
                organization_id=org1.id,
                name="Residential Complex - Building A",
                description="New construction of 50-unit residential building",
                status="active",
            )
            project3 = Project(
                organization_id=org2.id,
                name="Highway Bridge Inspection",
                description="Annual inspection and damage assessment",
                status="completed",
            )
            session.add_all([project1, project2, project3])
            await session.flush()
            print("✓ Created projects")

            # Create photos
            photo1 = Photo(
                user_id=user1.id,
                project_id=project1.id,
                s3_url="https://s3.amazonaws.com/companycam-photos/test/photo1.jpg",
                s3_key="test/photo1.jpg",
                file_size_bytes=2048576,
                mime_type="image/jpeg",
                width=4032,
                height=3024,
                exif_data={
                    "camera": "iPhone 13 Pro",
                    "gps": {"lat": 40.7128, "lon": -74.0060},
                    "timestamp": "2025-11-15T10:30:00Z",
                },
                uploaded_at=datetime.utcnow() - timedelta(days=2),
            )
            photo2 = Photo(
                user_id=user1.id,
                project_id=project1.id,
                s3_url="https://s3.amazonaws.com/companycam-photos/test/photo2.jpg",
                s3_key="test/photo2.jpg",
                file_size_bytes=1843200,
                mime_type="image/jpeg",
                width=4032,
                height=3024,
                exif_data={
                    "camera": "iPhone 13 Pro",
                    "gps": {"lat": 40.7129, "lon": -74.0061},
                    "timestamp": "2025-11-15T14:20:00Z",
                },
                uploaded_at=datetime.utcnow() - timedelta(days=1),
            )
            photo3 = Photo(
                user_id=user3.id,
                project_id=project3.id,
                s3_url="https://s3.amazonaws.com/companycam-photos/test/photo3.jpg",
                s3_key="test/photo3.jpg",
                file_size_bytes=3145728,
                mime_type="image/jpeg",
                width=3840,
                height=2160,
                exif_data={
                    "camera": "Canon EOS R5",
                    "gps": {"lat": 41.8781, "lon": -87.6298},
                    "timestamp": "2025-11-10T09:15:00Z",
                },
                uploaded_at=datetime.utcnow() - timedelta(days=7),
            )
            session.add_all([photo1, photo2, photo3])
            await session.flush()
            print("✓ Created photos")

            # Create detections
            detection1 = Detection(
                photo_id=photo1.id,
                detection_type="damage",
                model_version="yolov8-damage-v1.0",
                results={
                    "detections": [
                        {
                            "class": "crack",
                            "confidence": 0.92,
                            "bbox": [100, 150, 300, 400],
                        },
                        {
                            "class": "water_damage",
                            "confidence": 0.78,
                            "bbox": [500, 200, 700, 500],
                        },
                    ]
                },
                confidence=0.92,
                processing_time_ms=245,
                user_confirmed=False,
            )
            detection2 = Detection(
                photo_id=photo2.id,
                detection_type="material",
                model_version="yolov8-material-v1.0",
                results={
                    "detections": [
                        {
                            "class": "concrete",
                            "confidence": 0.95,
                            "bbox": [0, 0, 4032, 3024],
                        }
                    ]
                },
                confidence=0.95,
                processing_time_ms=198,
                user_confirmed=True,
                user_feedback={"notes": "Correct identification"},
            )
            detection3 = Detection(
                photo_id=photo3.id,
                detection_type="damage",
                model_version="yolov8-damage-v1.0",
                results={
                    "detections": [
                        {
                            "class": "rust",
                            "confidence": 0.88,
                            "bbox": [1200, 800, 1800, 1500],
                        }
                    ]
                },
                confidence=0.88,
                processing_time_ms=312,
                user_confirmed=True,
            )
            session.add_all([detection1, detection2, detection3])
            await session.flush()
            print("✓ Created detections")

            # Create tags
            tag1 = Tag(
                photo_id=photo1.id,
                tag="crack",
                source="ai",
                confidence=0.92,
            )
            tag2 = Tag(
                photo_id=photo1.id,
                tag="water damage",
                source="ai",
                confidence=0.78,
            )
            tag3 = Tag(
                photo_id=photo1.id,
                tag="needs repair",
                source="user",
                confidence=None,
            )
            tag4 = Tag(
                photo_id=photo2.id,
                tag="concrete",
                source="ai",
                confidence=0.95,
            )
            tag5 = Tag(
                photo_id=photo3.id,
                tag="rust",
                source="ai",
                confidence=0.88,
            )
            tag6 = Tag(
                photo_id=photo3.id,
                tag="bridge inspection",
                source="user",
                confidence=None,
            )
            session.add_all([tag1, tag2, tag3, tag4, tag5, tag6])
            await session.flush()
            print("✓ Created tags")

            await session.commit()
            print("\n✅ Database seeding completed successfully!")

            # Print summary
            print("\nSummary:")
            print(f"  - Organizations: 2")
            print(f"  - Users: 3")
            print(f"  - Projects: 3")
            print(f"  - Photos: 3")
            print(f"  - Detections: 3")
            print(f"  - Tags: 6")

        except Exception as e:
            await session.rollback()
            print(f"❌ Error seeding database: {e}")
            raise


async def main():
    """Main function"""
    print("Starting database seeding...\n")

    # Optionally create tables first (useful for fresh databases)
    # Uncomment the next line if you want to create tables before seeding
    # await create_tables()

    await seed_data()


if __name__ == "__main__":
    asyncio.run(main())
