"""RFC 7807 Problem Details error response formatting"""

from typing import Optional, Dict, Any, List
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class ValidationErrorDetail(BaseModel):
    """Validation error detail for a specific field"""
    field: str
    message: str


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details for HTTP APIs"""
    type: str = Field(..., description="URI reference identifying the problem type")
    title: str = Field(..., description="Short, human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation")
    instance: Optional[str] = Field(None, description="URI reference identifying the specific occurrence")
    errors: Optional[List[ValidationErrorDetail]] = Field(None, description="Validation errors")


def create_error_response(
    status_code: int,
    title: str,
    detail: str,
    error_type: Optional[str] = None,
    instance: Optional[str] = None,
    errors: Optional[List[Dict[str, str]]] = None
) -> JSONResponse:
    """
    Create an RFC 7807 compliant error response

    Args:
        status_code: HTTP status code
        title: Short error title
        detail: Detailed error message
        error_type: Error type URI (defaults to generic type based on status code)
        instance: Request path or identifier
        errors: List of validation errors with field and message

    Returns:
        JSONResponse with problem details
    """
    # Default error types based on status code
    error_type_map = {
        400: "validation_error",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        500: "internal_server_error",
        502: "bad_gateway",
        503: "service_unavailable"
    }

    if not error_type:
        error_type = error_type_map.get(status_code, "error")

    problem = {
        "type": f"https://api.companycam.com/errors/{error_type}",
        "title": title,
        "status": status_code,
        "detail": detail
    }

    if instance:
        problem["instance"] = instance

    if errors:
        problem["errors"] = errors

    return JSONResponse(
        status_code=status_code,
        content=problem
    )


def unauthorized_error(detail: str = "Authentication required", instance: Optional[str] = None) -> JSONResponse:
    """Create a 401 Unauthorized error response"""
    return create_error_response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        title="Unauthorized",
        detail=detail,
        instance=instance
    )


def forbidden_error(detail: str = "Insufficient permissions", instance: Optional[str] = None) -> JSONResponse:
    """Create a 403 Forbidden error response"""
    return create_error_response(
        status_code=status.HTTP_403_FORBIDDEN,
        title="Forbidden",
        detail=detail,
        instance=instance
    )


def not_found_error(detail: str = "Resource not found", instance: Optional[str] = None) -> JSONResponse:
    """Create a 404 Not Found error response"""
    return create_error_response(
        status_code=status.HTTP_404_NOT_FOUND,
        title="Not Found",
        detail=detail,
        instance=instance
    )


def validation_error(
    detail: str = "Validation failed",
    errors: Optional[List[Dict[str, str]]] = None,
    instance: Optional[str] = None
) -> JSONResponse:
    """Create a 400 Validation Error response"""
    return create_error_response(
        status_code=status.HTTP_400_BAD_REQUEST,
        title="Validation Error",
        detail=detail,
        errors=errors,
        instance=instance
    )


def conflict_error(detail: str = "Resource conflict", instance: Optional[str] = None) -> JSONResponse:
    """Create a 409 Conflict error response"""
    return create_error_response(
        status_code=status.HTTP_409_CONFLICT,
        title="Conflict",
        detail=detail,
        instance=instance
    )


def internal_server_error(
    detail: str = "An internal server error occurred",
    instance: Optional[str] = None
) -> JSONResponse:
    """Create a 500 Internal Server Error response"""
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Internal Server Error",
        detail=detail,
        instance=instance
    )
