"""Project management endpoints"""

from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import datetime

from src.database import get_db
from src.models.project import Project
from src.models.photo import Photo
from src.api.middleware import AuthMiddleware, security
from src.schemas.project import (
    ProjectResponse,
    ProjectDetailResponse,
    ProjectUpdate,
    ProjectListResponse
)
from src.api.errors import not_found_error, forbidden_error, validation_error

router = APIRouter(prefix="/api/v1/projects", tags=["Projects"])


@router.get("", response_model=ProjectListResponse, status_code=status.HTTP_200_OK)
async def get_projects(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(AuthMiddleware.get_current_user)
):
    """
    Get all projects for the authenticated user's organization

    Returns paginated list of projects
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Authentication required",
                "instance": request.url.path
            }
        )

    organization_id = current_user.get("organization_id")

    # Get total count
    count_result = await db.execute(
        select(func.count(Project.id)).where(
            Project.organization_id == organization_id
        )
    )
    total = count_result.scalar_one()

    # Get paginated projects
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Project)
        .where(Project.organization_id == organization_id)
        .order_by(Project.created_at.desc())
        .limit(page_size)
        .offset(offset)
    )
    projects = result.scalars().all()

    return ProjectListResponse(
        projects=[ProjectResponse.model_validate(p) for p in projects],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{project_id}", response_model=ProjectDetailResponse, status_code=status.HTTP_200_OK)
async def get_project(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(AuthMiddleware.get_current_user)
):
    """
    Get detailed information about a specific project

    Returns project details including photo count and last photo timestamp
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Authentication required",
                "instance": request.url.path
            }
        )

    organization_id = current_user.get("organization_id")

    # Get project
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://api.companycam.com/errors/not_found",
                "title": "Not Found",
                "status": 404,
                "detail": f"Project with id {project_id} not found",
                "instance": request.url.path
            }
        )

    # Verify user has access (same organization)
    if str(project.organization_id) != organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://api.companycam.com/errors/not_found",
                "title": "Not Found",
                "status": 404,
                "detail": f"Project with id {project_id} not found",
                "instance": request.url.path
            }
        )

    # Get photo count and last photo timestamp
    photo_count_result = await db.execute(
        select(func.count(Photo.id)).where(Photo.project_id == project_id)
    )
    photo_count = photo_count_result.scalar_one() or 0

    last_photo_result = await db.execute(
        select(Photo.created_at)
        .where(Photo.project_id == project_id)
        .order_by(Photo.created_at.desc())
        .limit(1)
    )
    last_photo = last_photo_result.scalar_one_or_none()

    # Build response
    project_dict = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "organization_id": project.organization_id,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "photo_count": photo_count,
        "last_photo_at": last_photo
    }

    return ProjectDetailResponse(**project_dict)


@router.patch("/{project_id}", response_model=ProjectResponse, status_code=status.HTTP_200_OK)
async def update_project(
    project_id: UUID,
    project_update: ProjectUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(AuthMiddleware.get_current_user)
):
    """
    Update project name, description, or status

    Only users from the same organization can update the project
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "type": "https://api.companycam.com/errors/unauthorized",
                "title": "Unauthorized",
                "status": 401,
                "detail": "Authentication required",
                "instance": request.url.path
            }
        )

    organization_id = current_user.get("organization_id")

    # Get project
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "type": "https://api.companycam.com/errors/not_found",
                "title": "Not Found",
                "status": 404,
                "detail": f"Project with id {project_id} not found",
                "instance": request.url.path
            }
        )

    # Verify user has access (same organization)
    if str(project.organization_id) != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "type": "https://api.companycam.com/errors/forbidden",
                "title": "Forbidden",
                "status": 403,
                "detail": "You do not have permission to update this project",
                "instance": request.url.path
            }
        )

    # Update fields
    update_data = project_update.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(project, field, value)

    # Update timestamp
    project.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(project)

    return ProjectResponse.model_validate(project)
