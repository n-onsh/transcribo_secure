"""Configuration models."""

from typing import List, Optional
from pydantic import BaseModel, Field

class KeyVaultConfig(BaseModel):
    """Key Vault configuration."""
    enabled: bool = Field(default=True, description="Whether Key Vault is enabled")
    mode: str = Field(default="local", description="Key Vault mode (local or azure)")
    url: Optional[str] = Field(default=None, description="Azure Key Vault URL")
    tenant_id: Optional[str] = Field(default=None, description="Azure tenant ID")
    client_id: Optional[str] = Field(default=None, description="Azure client ID")
    client_secret: Optional[str] = Field(default=None, description="Azure client secret")
    cache_enabled: bool = Field(default=True, description="Whether to enable caching")
    cache_duration_minutes: int = Field(default=60, description="Cache duration in minutes")
    local_path: str = Field(default="secrets", description="Path for local secrets storage")

class EncryptionConfig(BaseModel):
    """Encryption configuration."""
    enabled: bool = Field(default=True, description="Whether encryption is enabled")
    algorithm: str = Field(default="AES-256-GCM", description="Encryption algorithm")
    key_rotation_days: int = Field(default=30, description="Key rotation interval in days")
    chunk_size_mb: int = Field(default=5, description="Chunk size for streaming encryption in MB")

class StorageConfig(BaseModel):
    """Storage configuration."""
    endpoint: str = Field(..., description="Storage endpoint")
    port: int = Field(default=9000, description="Storage port")
    access_key: str = Field(..., description="Storage access key")
    secret_key: str = Field(..., description="Storage secret key")
    bucket_name: str = Field(default="transcribo", description="Storage bucket name")
    region: str = Field(default="us-east-1", description="Storage region")
    secure: bool = Field(default=True, description="Whether to use HTTPS")
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)
    key_vault: KeyVaultConfig = Field(default_factory=KeyVaultConfig)

class AuthConfig(BaseModel):
    """Authentication configuration."""
    mode: str = Field(default="jwt", description="Authentication mode (jwt or azure)")
    jwt_secret: Optional[str] = Field(default=None, description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expires_minutes: int = Field(default=60, description="JWT expiration in minutes")
    azure_tenant_id: Optional[str] = Field(default=None, description="Azure AD tenant ID")
    azure_client_id: Optional[str] = Field(default=None, description="Azure AD client ID")

class Config(BaseModel):
    """Application configuration."""
    auth: AuthConfig = Field(default_factory=AuthConfig)
    storage: StorageConfig
