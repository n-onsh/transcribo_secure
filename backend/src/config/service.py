"""Configuration service."""

import os
from typing import Dict, Any, Optional, Type, TypeVar, Generic, cast
from pydantic import BaseModel, ValidationError
from .models import AppConfig

class ConfigurationService:
    """Configuration service."""
    
    _instance = None
    
    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super(ConfigurationService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize configuration service."""
        if self._initialized:
            return
            
        self._initialized = True
        self.config = self._load_config()
    
    def _load_config(self) -> AppConfig:
        """Load configuration from environment variables.
        
        Returns:
            Configuration object
        """
        # Create configuration dictionary from environment variables
        config_dict = self._load_env_vars()
        
        # Create configuration object
        try:
            return AppConfig(**config_dict)
        except ValidationError as e:
            # Print validation errors
            print(f"Configuration validation error: {e}")
            raise
    
    def _load_env_vars(self) -> Dict[str, Any]:
        """Load configuration from environment variables.
        
        Returns:
            Configuration dictionary
        """
        config_dict = {}
        
        # Environment variable mappings
        env_mappings = {
            # Database
            "POSTGRES_HOST": "database.host",
            "POSTGRES_PORT": "database.port",
            "POSTGRES_DB": "database.database",
            "POSTGRES_USER": "database.username",
            "POSTGRES_PASSWORD": "database.password",
            
            # Authentication
            "AUTH_MODE": "auth.mode",
            "AZURE_TENANT_ID": "auth.azure_tenant_id",
            "AZURE_CLIENT_ID": "auth.azure_client_id",
            "AZURE_CLIENT_SECRET": "auth.azure_client_secret",
            "JWT_SECRET_KEY": "auth.jwt_secret_key",
            "JWT_ALGORITHM": "auth.jwt_algorithm",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "auth.jwt_access_token_expire_minutes",
            "JWT_REFRESH_TOKEN_EXPIRE_MINUTES": "auth.jwt_refresh_token_expire_minutes",
            "JWT_AUDIENCE": "auth.jwt_audience",
            "JWT_ISSUER": "auth.jwt_issuer",
            
            # Storage
            "MINIO_HOST": "storage.minio_endpoint",
            "MINIO_PORT": "storage.minio_port",
            "MINIO_ACCESS_KEY": "storage.minio_access_key",
            "MINIO_SECRET_KEY": "storage.minio_secret_key",
            "MINIO_BUCKET": "storage.bucket_name",
            "MINIO_SECURE": "storage.minio_secure",
            "MINIO_REGION": "storage.minio_region",
            "MAX_FILE_SIZE": "storage.max_file_size",
            "ALLOWED_EXTENSIONS": "storage.allowed_extensions",
            "STORAGE_PATH": "storage.local_storage_path",
            
            # Transcriber
            "DEVICE": "transcriber.device",
            "BATCH_SIZE": "transcriber.batch_size",
            "COMPUTE_TYPE": "transcriber.compute_type",
            "DEFAULT_LANGUAGE": "transcriber.language",
            "SUPPORTED_LANGUAGES": "transcriber.supported_languages",
            "WORKER_COUNT": "transcriber.worker_count",
            "TRANSCRIBER_REPLICAS": "transcriber.replicas",
            
            # Application
            "ENVIRONMENT": "environment",
            "LOG_LEVEL": "log_level",
            "HOST": "host",
            "PORT": "port",
            "WORKERS": "workers",
        }
        
        # Get all environment variables
        for env_var, config_path in env_mappings.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                
                # Handle special cases
                if env_var == "ALLOWED_EXTENSIONS":
                    value = value.split(",")
                elif env_var == "SUPPORTED_LANGUAGES":
                    value = value.split(",")
                else:
                    value = self._convert_value(value)
                
                # Set value in configuration dictionary
                self._set_nested_dict_value(config_dict, config_path, value)
        
        return config_dict
    
    def _set_nested_dict_value(self, d: Dict[str, Any], key: str, value: Any) -> None:
        """Set value in nested dictionary.
        
        Args:
            d: Dictionary to set value in
            key: Key to set (can be nested with dots)
            value: Value to set
        """
        # Split key by dots
        keys = key.split(".")
        
        # Traverse dictionary
        for i, k in enumerate(keys[:-1]):
            if k not in d:
                d[k] = {}
            elif not isinstance(d[k], dict):
                d[k] = {}
            d = d[k]
        
        # Set value
        d[keys[-1]] = value
    
    def _convert_value(self, value: str) -> Any:
        """Convert string value to appropriate type.
        
        Args:
            value: String value
            
        Returns:
            Converted value
        """
        # Convert to boolean
        if value.lower() in ["true", "yes", "1"]:
            return True
        elif value.lower() in ["false", "no", "0"]:
            return False
            
        # Convert to integer
        try:
            return int(value)
        except ValueError:
            pass
            
        # Convert to float
        try:
            return float(value)
        except ValueError:
            pass
            
        # Return as string
        return value
    
    def get_config(self) -> AppConfig:
        """Get configuration.
        
        Returns:
            Configuration object
        """
        return self.config
