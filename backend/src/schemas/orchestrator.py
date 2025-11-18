"""Pydantic schemas for AI Orchestrator service"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import UUID, uuid4
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict


class DetectionType(str, Enum):
    """Supported detection types"""
    DAMAGE = "damage"
    MATERIAL = "material"
    VOLUME = "volume"


class Priority(str, Enum):
    """Request priority levels"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DetectionStatus(str, Enum):
    """Detection request status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


class DetectionRequest(BaseModel):
    """Schema for AI detection request"""
    photo_id: UUID
    photo_url: str = Field(..., description="S3 URL or path to the photo")
    detection_types: List[DetectionType] = Field(
        default=[DetectionType.DAMAGE, DetectionType.MATERIAL],
        description="List of detection types to run"
    )
    priority: Priority = Field(default=Priority.NORMAL, description="Request priority level")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('photo_url')
    @classmethod
    def validate_photo_url(cls, v: str) -> str:
        """Validate photo URL format"""
        if not v or len(v.strip()) == 0:
            raise ValueError("Photo URL cannot be empty")
        return v.strip()


class ModelVersion(BaseModel):
    """Model version information"""
    model_config = ConfigDict(protected_namespaces=())

    name: str
    version: str
    engine_type: DetectionType
    endpoint: Optional[str] = None
    confidence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    enabled: bool = True


class EngineResult(BaseModel):
    """Result from a single detection engine"""
    model_config = ConfigDict(protected_namespaces=())

    engine_type: DetectionType
    model_version: str
    confidence: float = Field(ge=0.0, le=1.0)
    results: Dict[str, Any] = Field(default_factory=dict)
    processing_time_ms: int
    error: Optional[str] = None


class DetectionResponse(BaseModel):
    """Schema for AI detection response"""
    model_config = ConfigDict(protected_namespaces=())

    request_id: UUID = Field(default_factory=uuid4)
    detection_id: UUID = Field(default_factory=uuid4)
    photo_id: UUID
    status: DetectionStatus
    results: Dict[str, EngineResult] = Field(default_factory=dict)
    processing_time_ms: int = 0
    model_versions: Dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    error: Optional[str] = None


class EngineHealth(BaseModel):
    """Health status of a detection engine"""
    engine_type: DetectionType
    endpoint: str
    healthy: bool
    last_check: datetime
    response_time_ms: Optional[int] = None
    error_count: int = 0
    consecutive_failures: int = 0


class CircuitBreakerState(str, Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


class ABTestConfig(BaseModel):
    """A/B testing configuration for model versions"""
    model_config = ConfigDict(protected_namespaces=())

    experiment_id: str
    model_a: ModelVersion
    model_b: ModelVersion
    traffic_split: float = Field(default=0.5, ge=0.0, le=1.0, description="% traffic to model A")
    enabled: bool = True


class LoadBalancerConfig(BaseModel):
    """Load balancer configuration"""
    strategy: str = Field(default="round_robin", description="Load balancing strategy")
    health_check_interval_seconds: int = Field(default=30, ge=5)
    circuit_breaker_threshold: int = Field(default=5, ge=1, description="Failures before opening circuit")
    circuit_breaker_timeout_seconds: int = Field(default=60, ge=10)


class OrchestratorMetrics(BaseModel):
    """Metrics collected by orchestrator"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_processing_time_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p90_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    error_rate: float = 0.0
    engine_metrics: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
