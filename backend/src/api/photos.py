"""Photo upload API routes"""

import logging
from typing import Optional
from datetime import datetime
from uuid import uuid4, UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.database import get_db
from src.models import Photo, Project, PhotoStatus
from src.schemas.photo import (
    PhotoUploadUrlRequest,
    PhotoUploadUrlResponse,
    PhotoResponse,
    PhotoStatusUpdate,
)
from src.services import S3Service, QueueService
from src.api.dependencies import get_current_user
from src.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/photos", tags=["photos"])


@router.post("/upload-url", response_model=PhotoUploadUrlResponse, status_code=status.HTTP_200_OK)
async def generate_upload_url(
    request: PhotoUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoUploadUrlResponse:
    """
    Generate pre-signed S3 URL for photo upload.

    This endpoint:
    1. Validates user has access to the project
    2. Validates file size and MIME type
    3. Generates a unique photo ID
    4. Creates a pre-signed S3 URL (15 min expiration)
    5. Creates a photo record in the database with 'pending_upload' status
    6. Returns upload URL and metadata

    Args:
        request: Upload URL request parameters
        current_user: Authenticated user
        db: Database session

    Returns:
        PhotoUploadUrlResponse with upload URL and metadata

    Raises:
        HTTPException 403: User doesn't have access to project
        HTTPException 404: Project not found
        HTTPException 400: Invalid file size or MIME type
        HTTPException 500: S3 or database error
    """
    # Verify project exists and user has access to it
    result = await db.execute(
        select(Project).where(Project.id == request.project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {request.project_id} not found",
        )

    # Check user has access to this project (same organization)
    if project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this project",
        )

    # Initialize S3 service
    try:
        s3_service = S3Service()
    except Exception as e:
        logger.error(f"Failed to initialize S3 service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="S3 service unavailable",
        )

    # Validate file
    try:
        s3_service.validate_file(request.file_size, request.mime_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Generate unique photo ID
    photo_id = uuid4()

    # Extract file extension from filename or mime type
    file_name = request.file_name.lower()
    if file_name.endswith(".jpg") or file_name.endswith(".jpeg"):
        extension = "jpg"
    elif file_name.endswith(".png"):
        extension = "png"
    else:
        # Default based on MIME type
        extension = "jpg" if request.mime_type == "image/jpeg" else "png"

    # Generate S3 key
    s3_key = s3_service.generate_s3_key(
        project_id=str(request.project_id),
        photo_id=str(photo_id),
        file_extension=extension,
    )

    # Generate pre-signed URL
    try:
        url_data = s3_service.generate_presigned_upload_url(
            s3_key=s3_key,
            mime_type=request.mime_type,
            file_size=request.file_size,
        )
    except Exception as e:
        logger.error(f"Failed to generate pre-signed URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL",
        )

    # Create photo record in database with pending_upload status
    photo = Photo(
        id=photo_id,
        user_id=current_user.id,
        project_id=request.project_id,
        s3_url=url_data["s3_url"],
        s3_key=s3_key,
        file_size_bytes=request.file_size,
        mime_type=request.mime_type,
        status=PhotoStatus.PENDING_UPLOAD,
    )

    try:
        db.add(photo)
        await db.commit()
        await db.refresh(photo)
        logger.info(f"Created photo record {photo_id} for user {current_user.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create photo record: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create photo record",
        )

    return PhotoUploadUrlResponse(
        upload_id=photo_id,
        photo_id=photo_id,
        upload_url=url_data["upload_url"],
        s3_url=url_data["s3_url"],
        expires_in_seconds=url_data["expires_in_seconds"],
        headers=url_data["headers"],
    )


@router.get("/{photo_id}", response_model=PhotoResponse)
async def get_photo(
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """
    Get photo details by ID.

    Args:
        photo_id: Photo UUID
        current_user: Authenticated user
        db: Database session

    Returns:
        PhotoResponse with photo details

    Raises:
        HTTPException 404: Photo not found
        HTTPException 403: User doesn't have access to photo
    """
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Photo {photo_id} not found",
        )

    # Verify user has access to this photo
    result = await db.execute(
        select(Project).where(Project.id == photo.project_id)
    )
    project = result.scalar_one_or_none()

    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this photo",
        )

    return PhotoResponse.model_validate(photo)


@router.patch("/{photo_id}/status", response_model=PhotoResponse)
async def update_photo_status(
    photo_id: UUID,
    status_update: PhotoStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PhotoResponse:
    """
    Update photo status.

    This endpoint is typically called after:
    - Client successfully uploads photo to S3 (status: uploaded)
    - Detection pipeline starts processing (status: processing)
    - Detection completes (status: completed)
    - Processing fails (status: failed)

    Args:
        photo_id: Photo UUID
        status_update: New status
        current_user: Authenticated user
        db: Database session

    Returns:
        PhotoResponse with updated photo details

    Raises:
        HTTPException 404: Photo not found
        HTTPException 403: User doesn't have access to photo
    """
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Photo {photo_id} not found",
        )

    # Verify user has access to this photo
    result = await db.execute(
        select(Project).where(Project.id == photo.project_id)
    )
    project = result.scalar_one_or_none()

    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this photo",
        )

    # Update status
    old_status = photo.status
    photo.status = PhotoStatus(status_update.status)

    # If status changed to 'uploaded', trigger detection pipeline
    if status_update.status == "uploaded" and old_status != PhotoStatus.UPLOADED:
        photo.uploaded_at = datetime.utcnow()

        # Try to publish to queue
        try:
            queue_service = QueueService()
            success = queue_service.publish_photo_detection_message(
                photo_id=str(photo_id),
                s3_url=photo.s3_url,
            )
            if success:
                logger.info(f"Published detection message for photo {photo_id}")
                # Update status to processing if message was published
                photo.status = PhotoStatus.PROCESSING
            else:
                logger.warning(
                    f"Failed to publish detection message for photo {photo_id}, "
                    "keeping status as uploaded"
                )
        except Exception as e:
            logger.error(f"Error publishing to queue: {e}")
            # Don't fail the request if queue is unavailable

    try:
        await db.commit()
        await db.refresh(photo)
        logger.info(f"Updated photo {photo_id} status: {old_status} -> {photo.status}")
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update photo status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update photo status",
        )

    return PhotoResponse.model_validate(photo)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(
    photo_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete photo by ID.

    This will:
    1. Verify user has access
    2. Delete photo record from database
    3. Optionally delete from S3 (can be done async)

    Args:
        photo_id: Photo UUID
        current_user: Authenticated user
        db: Database session

    Raises:
        HTTPException 404: Photo not found
        HTTPException 403: User doesn't have access to photo
    """
    result = await db.execute(
        select(Photo).where(Photo.id == photo_id)
    )
    photo = result.scalar_one_or_none()

    if not photo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Photo {photo_id} not found",
        )

    # Verify user has access to this photo
    result = await db.execute(
        select(Project).where(Project.id == photo.project_id)
    )
    project = result.scalar_one_or_none()

    if not project or project.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this photo",
        )

    try:
        await db.delete(photo)
        await db.commit()
        logger.info(f"Deleted photo {photo_id}")

        # Optionally delete from S3 (done in background in production)
        try:
            s3_service = S3Service()
            if photo.s3_key:
                s3_service.delete_object(photo.s3_key)
                logger.info(f"Deleted S3 object: {photo.s3_key}")
        except Exception as e:
            logger.error(f"Failed to delete S3 object: {e}")
            # Don't fail the request if S3 deletion fails

    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete photo: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete photo",
        )
