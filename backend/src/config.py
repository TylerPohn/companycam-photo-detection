"""Application configuration using Pydantic Settings"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # AWS / S3
    aws_region: str = "us-east-1"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_endpoint_url: Optional[str] = None
    s3_bucket: str = "companycam-photos"

    # Security
    secret_key: str
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Logging
    log_level: str = "INFO"

    # ML Models
    ml_model_path: str = "/app/ml-models/models"
    ml_confidence_threshold: float = 0.75

    # Rate Limiting
    rate_limit_per_minute: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into a list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


# Global settings instance
settings = Settings()
