"""Unit tests for configuration service."""

import os
import pytest
from src.config import (
    AppConfig,
    DatabaseConfig,
    AuthConfig,
    StorageConfig,
    TranscriberConfig,
    ConfigurationService
)

@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables."""
    env_vars = {
        # Database
        "POSTGRES_HOST": "test-host",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "test-db",
        "POSTGRES_USER": "test-user",
        "POSTGRES_PASSWORD": "test-password",
        
        # Authentication
        "AUTH_MODE": "jwt",
        "JWT_SECRET_KEY": "test-secret",
        "JWT_ALGORITHM": "HS256",
        "JWT_ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        "JWT_REFRESH_TOKEN_EXPIRE_MINUTES": "1440",
        "JWT_AUDIENCE": "test-audience",
        "JWT_ISSUER": "test-issuer",
        
        # Storage
        "MINIO_HOST": "test-minio",
        "MINIO_PORT": "9000",
        "MINIO_ACCESS_KEY": "test-access",
        "MINIO_SECRET_KEY": "test-secret",
        "MINIO_BUCKET": "test-bucket",
        "MINIO_SECURE": "false",
        "MINIO_REGION": "test-region",
        "MAX_FILE_SIZE": "104857600",
        "ALLOWED_EXTENSIONS": ".mp3,.wav,.m4a",
        "STORAGE_PATH": "/test/path",
        
        # Transcriber
        "DEVICE": "cpu",
        "BATCH_SIZE": "32",
        "COMPUTE_TYPE": "float16",
        "DEFAULT_LANGUAGE": "en",
        "SUPPORTED_LANGUAGES": "de,en,fr,it",
        "WORKER_COUNT": "1",
        "TRANSCRIBER_REPLICAS": "1",
        
        # Application
        "ENVIRONMENT": "testing",
        "LOG_LEVEL": "debug",
        "HOST": "0.0.0.0",
        "PORT": "8000",
        "WORKERS": "1",
    }
    
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    
    return env_vars

def test_singleton_instance():
    """Test that ConfigurationService is a singleton."""
    service1 = ConfigurationService()
    service2 = ConfigurationService()
    assert service1 is service2

def test_config_loading(mock_env):
    """Test configuration loading from environment variables."""
    service = ConfigurationService()
    config = service.get_config()
    
    # Test database configuration
    assert config.database.host == "test-host"
    assert config.database.port == 5432
    assert config.database.database == "test-db"
    assert config.database.username == "test-user"
    assert config.database.password == "test-password"
    
    # Test authentication configuration
    assert config.auth.mode == "jwt"
    assert config.auth.jwt_secret_key == "test-secret"
    assert config.auth.jwt_algorithm == "HS256"
    assert config.auth.jwt_access_token_expire_minutes == 60
    assert config.auth.jwt_refresh_token_expire_minutes == 1440
    assert config.auth.jwt_audience == "test-audience"
    assert config.auth.jwt_issuer == "test-issuer"
    
    # Test storage configuration
    assert config.storage.provider == "minio"
    assert config.storage.minio_endpoint == "test-minio"
    assert config.storage.minio_port == 9000
    assert config.storage.minio_access_key == "test-access"
    assert config.storage.minio_secret_key == "test-secret"
    assert config.storage.bucket_name == "test-bucket"
    assert config.storage.minio_secure is False
    assert config.storage.minio_region == "test-region"
    assert config.storage.max_file_size == 104857600
    assert config.storage.allowed_extensions == [".mp3", ".wav", ".m4a"]
    assert config.storage.local_storage_path == "/test/path"
    
    # Test transcriber configuration
    assert config.transcriber.device == "cpu"
    assert config.transcriber.batch_size == 32
    assert config.transcriber.compute_type == "float16"
    assert config.transcriber.language == "en"
    assert config.transcriber.supported_languages == ["de", "en", "fr", "it"]
    assert config.transcriber.worker_count == 1
    assert config.transcriber.replicas == 1
    
    # Test application configuration
    assert config.environment == "testing"
    assert config.log_level == "debug"
    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.workers == 1

def test_default_values():
    """Test default configuration values."""
    service = ConfigurationService()
    config = service.get_config()
    
    # Test database defaults
    assert config.database.pool_size == 5
    assert config.database.max_overflow == 10
    assert config.database.pool_timeout == 30
    assert config.database.pool_recycle == 1800
    
    # Test storage defaults
    assert config.storage.provider == "minio"
    assert config.storage.encryption_enabled is True
    
    # Test transcriber defaults
    assert config.transcriber.task == "transcribe"
    assert config.transcriber.beam_size == 5

def test_validation_error(mock_env, monkeypatch):
    """Test configuration validation error."""
    # Set invalid value
    monkeypatch.setenv("DEVICE", "invalid")
    
    with pytest.raises(Exception) as excinfo:
        ConfigurationService()
    
    assert "validation error" in str(excinfo.value).lower()

def test_connection_string():
    """Test database connection string generation."""
    config = DatabaseConfig(
        host="localhost",
        port=5432,
        database="test",
        username="user",
        password="pass"
    )
    
    assert config.connection_string == "postgresql://user:pass@localhost:5432/test"

def test_minio_url():
    """Test MinIO URL generation."""
    config = StorageConfig(
        minio_endpoint="localhost",
        minio_port=9000,
        minio_secure=True
    )
    
    assert config.minio_url == "https://localhost:9000"
    
    config.minio_secure = False
    assert config.minio_url == "http://localhost:9000"
    
    config.minio_endpoint = None
    assert config.minio_url == ""

def test_value_conversion():
    """Test environment variable value conversion."""
    service = ConfigurationService()
    
    # Test boolean conversion
    assert service._convert_value("true") is True
    assert service._convert_value("yes") is True
    assert service._convert_value("1") is True
    assert service._convert_value("false") is False
    assert service._convert_value("no") is False
    assert service._convert_value("0") is False
    
    # Test integer conversion
    assert service._convert_value("123") == 123
    
    # Test float conversion
    assert service._convert_value("123.45") == 123.45
    
    # Test string passthrough
    assert service._convert_value("test") == "test"
