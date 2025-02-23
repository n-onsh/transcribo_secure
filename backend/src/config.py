"""
Application configuration.

Loads settings from environment variables with defaults.
"""
from functools import lru_cache
from pydantic import BaseSettings

class Settings(BaseSettings):
    """Application settings."""
    
    # File upload settings
    MAX_UPLOAD_SIZE: int = 12_000_000_000  # 12GB
    ALLOWED_FILE_TYPES: set = {
        'audio/mpeg',
        'audio/wav',
        'audio/ogg',
        'audio/x-wav',
        'video/mp4',
        'video/mpeg'
    }
    
    # Storage settings
    MINIO_HOST: str = "localhost"
    MINIO_PORT: str = "9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_REGION: str = "us-east-1"
    MINIO_SECURE: bool = False
    
    # Azure settings
    AZURE_KEYVAULT_URL: str = ""
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_CLIENT_SECRET: str = ""
    
    class Config:
        """Pydantic config."""
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
