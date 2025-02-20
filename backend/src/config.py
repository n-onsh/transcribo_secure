from pydantic import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Database settings
    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    # MinIO settings
    MINIO_HOST: str
    MINIO_PORT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool = False  # Set to True in production

    # Azure Key Vault settings
    AZURE_KEYVAULT_URL: str
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None

    # Application settings
    MAX_UPLOAD_SIZE: int = 1024 * 1024 * 1024  # 1GB
    CHUNK_SIZE: int = 1024 * 1024 * 5  # 5MB for multipart uploads
    ALLOWED_FILE_TYPES: list[str] = [
        'audio/mpeg', 'audio/wav', 'audio/ogg',
        'video/mp4', 'video/mpeg', 'video/ogg'
    ]
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    """Cached settings to avoid reading .env file multiple times"""
    return Settings()