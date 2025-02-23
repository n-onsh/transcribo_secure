"""
Application configuration.

Loads and validates settings from environment variables.
"""
from functools import lru_cache
from pydantic import BaseSettings, validator, AnyHttpUrl, Field
from typing import Set, Optional, Dict
import os

class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Database settings
    POSTGRES_HOST: str = Field(..., description="PostgreSQL host")
    POSTGRES_PORT: int = Field(5432, description="PostgreSQL port")
    POSTGRES_DB: str = Field(..., description="PostgreSQL database name")
    POSTGRES_USER: str = Field(..., description="PostgreSQL user")
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    
    # File upload settings
    MAX_UPLOAD_SIZE: int = Field(
        12_000_000_000,  # 12GB
        ge=1_000_000,  # Min 1MB
        le=50_000_000_000,  # Max 50GB
        description="Maximum file upload size in bytes"
    )
    ALLOWED_FILE_TYPES: Set[str] = Field(
        default={
            'audio/mpeg',
            'audio/wav',
            'audio/ogg',
            'audio/x-wav',
            'video/mp4',
            'video/mpeg'
        },
        description="Allowed file MIME types"
    )
    
    # Storage settings
    MINIO_HOST: str = Field(..., description="MinIO host")
    MINIO_PORT: str = Field(..., description="MinIO port")
    MINIO_ACCESS_KEY: str = Field(..., description="MinIO access key")
    MINIO_SECRET_KEY: str = Field(..., description="MinIO secret key")
    MINIO_REGION: str = Field("us-east-1", description="MinIO region")
    MINIO_SECURE: bool = Field(False, description="Use TLS for MinIO")
    
    # Azure KeyVault settings (optional)
    AZURE_KEYVAULT_URL: Optional[AnyHttpUrl] = Field(None, description="Azure KeyVault URL")
    AZURE_TENANT_ID: Optional[str] = Field(None, description="Azure tenant ID")
    AZURE_CLIENT_ID: Optional[str] = Field(None, description="Azure client ID")
    AZURE_CLIENT_SECRET: Optional[str] = Field(None, description="Azure client secret")
    
    # Transcriber settings
    TRANSCRIBER_URL: AnyHttpUrl = Field(..., description="Transcriber service URL")
    MAX_CONCURRENT_JOBS: int = Field(4, ge=1, le=16, description="Maximum concurrent transcription jobs")
    JOB_TIMEOUT_MINUTES: int = Field(120, ge=5, le=1440, description="Job timeout in minutes")
    JOB_CLEANUP_DAYS: int = Field(30, ge=1, le=365, description="Days to keep completed jobs")
    
    # Security settings
    CORS_ORIGINS: Set[str] = Field(
        default={'http://localhost:3000', 'https://localhost:3000'},
        description="Allowed CORS origins"
    )
    CORS_METHODS: Set[str] = Field(
        default={'GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'},
        description="Allowed HTTP methods"
    )
    CORS_HEADERS: Set[str] = Field(
        default={
            'Authorization',
            'Content-Type',
            'X-Request-ID',
            'X-Real-IP',
            'X-Forwarded-For'
        },
        description="Allowed HTTP headers"
    )
    CORS_MAX_AGE: int = Field(3600, ge=0, description="CORS preflight max age in seconds")
    CSP_DIRECTIVES: Dict[str, str] = Field(
        default={
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
            'style-src': "'self' 'unsafe-inline'",
            'img-src': "'self' data:",
            'font-src': "'self'",
            'object-src': "'none'",
            'base-uri': "'self'",
            'form-action': "'self'",
            'frame-ancestors': "'none'"
        },
        description="Content Security Policy directives"
    )
    
    @validator('AZURE_CLIENT_SECRET')
    def validate_azure_settings(cls, v, values):
        """Validate that all Azure settings are provided if any are."""
        azure_settings = [
            values.get('AZURE_KEYVAULT_URL'),
            values.get('AZURE_TENANT_ID'),
            values.get('AZURE_CLIENT_ID'),
            v
        ]
        if any(azure_settings) and not all(azure_settings):
            raise ValueError(
                "All Azure KeyVault settings must be provided if using Azure KeyVault"
            )
        return v
    
    @validator('POSTGRES_HOST')
    def validate_postgres_host(cls, v):
        """Validate PostgreSQL host."""
        if not v:
            raise ValueError("PostgreSQL host cannot be empty")
        return v
    
    @validator('MINIO_HOST')
    def validate_minio_host(cls, v):
        """Validate MinIO host."""
        if not v:
            raise ValueError("MinIO host cannot be empty")
        return v
    
    class Config:
        """Pydantic config."""
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance with validation."""
    try:
        return Settings()
    except Exception as e:
        raise RuntimeError(f"Configuration error: {str(e)}") from e

def validate_environment():
    """Validate all environment variables at startup."""
    get_settings()
