"""Main FastAPI application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from src.api.photos import router as photos_router
from src.api.auth import router as auth_router
from src.api.projects import router as projects_router
from src.api.health import router as health_router
from src.api.orchestrator import router as orchestrator_router
from src.api.detection_routes import router as detection_router
from src.api.feedback_routes import router as feedback_router
from src.api.report_routes import router as report_router
from src.api.websocket_routes import router as websocket_router
from src.config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

app = FastAPI(
    title="CompanyCam Photo Detection API",
    description="Backend API for photo detection and classification system with JWT authentication",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)

# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(photos_router)
app.include_router(orchestrator_router)
app.include_router(detection_router)
app.include_router(feedback_router)
app.include_router(report_router)
app.include_router(websocket_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "CompanyCam Photo Detection API",
        "version": "1.0.0",
        "status": "running",
    }
