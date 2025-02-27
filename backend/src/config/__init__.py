"""Configuration module."""

from .models import (
    AppConfig,
    DatabaseConfig,
    AuthConfig,
    StorageConfig,
    TranscriberConfig
)
from .service import ConfigurationService

# Create singleton instance
config_service = ConfigurationService()

# Export config instance
config = config_service.get_config()

__all__ = [
    'config',
    'config_service',
    'AppConfig',
    'DatabaseConfig',
    'AuthConfig',
    'StorageConfig',
    'TranscriberConfig',
    'ConfigurationService'
]
