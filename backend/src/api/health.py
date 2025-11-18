"""Health check endpoints"""

from fastapi import APIRouter, status
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import text
from src.database import get_db
from src.services.redis_service import RedisService
import boto3
from botocore.exceptions import ClientError
from src.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def basic_health_check():
    """
    Basic health check endpoint (no authentication required)

    Returns simple health status and timestamp
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@router.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def detailed_health_check():
    """
    Detailed health check with service dependency status (no authentication required)

    Checks connectivity to:
    - Database (PostgreSQL)
    - Redis
    - S3 (AWS)

    Returns overall status and individual service statuses
    """
    services = {}
    overall_status = "healthy"

    # Check database connectivity
    try:
        async for db in get_db():
            result = await db.execute(text("SELECT 1"))
            result.scalar_one()
            services["database"] = "connected"
            break
    except Exception as e:
        services["database"] = f"disconnected: {str(e)}"
        overall_status = "degraded"

    # Check Redis connectivity
    try:
        redis_service = RedisService()
        client = await redis_service.get_client()
        await client.ping()
        services["redis"] = "connected"
    except Exception as e:
        services["redis"] = f"disconnected: {str(e)}"
        overall_status = "degraded"

    # Check S3 connectivity
    try:
        s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.aws_endpoint_url
        )
        # Try to list buckets as a connectivity check
        s3_client.head_bucket(Bucket=settings.s3_bucket)
        services["s3"] = "connected"
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "404":
            services["s3"] = f"bucket_not_found: {settings.s3_bucket}"
        else:
            services["s3"] = f"disconnected: {error_code}"
        overall_status = "degraded"
    except Exception as e:
        services["s3"] = f"disconnected: {str(e)}"
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services
    }
