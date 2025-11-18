"""API routes for AI Orchestrator service"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Header, Depends
from fastapi.responses import JSONResponse

from src.schemas.orchestrator import (
    DetectionRequest,
    DetectionResponse,
    OrchestratorMetrics,
)
from src.services.ai_orchestrator import AIOrchestrator
from src.api.dependencies import get_current_user
from src.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestrator"])

# Global orchestrator instance
orchestrator = AIOrchestrator()


@router.post("/detect", response_model=DetectionResponse)
async def create_detection_request(
    request: DetectionRequest,
    x_correlation_id: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
) -> DetectionResponse:
    """
    Create a new detection request and process it through the orchestrator.

    Args:
        request: DetectionRequest with photo and detection types
        x_correlation_id: Optional correlation ID for distributed tracing
        current_user: Authenticated user

    Returns:
        DetectionResponse with results from all requested engines
    """
    try:
        logger.info(
            f"User {current_user.id} requesting detection for photo {request.photo_id}"
        )

        # Add user info to metadata
        request.metadata["user_id"] = str(current_user.id)

        # Process through orchestrator
        response = await orchestrator.process_detection_request(
            request=request,
            correlation_id=x_correlation_id,
        )

        return response

    except Exception as e:
        logger.error(f"Error processing detection request: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process detection request: {str(e)}"
        )


@router.get("/health")
async def get_orchestrator_health():
    """
    Get health status of orchestrator and all connected engines.

    Returns:
        Health status information
    """
    try:
        health_status = await orchestrator.get_health_status()
        return health_status

    except Exception as e:
        logger.error(f"Error getting health status: {e}", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@router.get("/metrics", response_model=OrchestratorMetrics)
async def get_orchestrator_metrics(
    current_user: User = Depends(get_current_user),
) -> OrchestratorMetrics:
    """
    Get orchestrator performance metrics.

    Args:
        current_user: Authenticated user

    Returns:
        OrchestratorMetrics with current statistics
    """
    try:
        metrics = orchestrator.get_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error getting metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get metrics: {str(e)}"
        )


@router.get("/status/{request_id}")
async def get_detection_status(
    request_id: UUID,
    current_user: User = Depends(get_current_user),
):
    """
    Get status of a specific detection request.

    Args:
        request_id: UUID of the detection request
        current_user: Authenticated user

    Returns:
        Detection request status
    """
    try:
        # Search in history
        for response in orchestrator.request_history:
            if response.request_id == request_id:
                return response

        raise HTTPException(
            status_code=404,
            detail=f"Detection request {request_id} not found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detection status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get detection status: {str(e)}"
        )


@router.get("/models")
async def get_available_models(
    current_user: User = Depends(get_current_user),
):
    """
    Get information about available detection models.

    Args:
        current_user: Authenticated user

    Returns:
        Dictionary of available models by detection type
    """
    try:
        models_info = {}
        for detection_type, models in orchestrator.model_registry.models.items():
            models_info[detection_type.value] = [
                {
                    "name": m.name,
                    "version": m.version,
                    "endpoint": m.endpoint,
                    "enabled": m.enabled,
                    "confidence_threshold": m.confidence_threshold,
                }
                for m in models
            ]

        return models_info

    except Exception as e:
        logger.error(f"Error getting model information: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get model information: {str(e)}"
        )
