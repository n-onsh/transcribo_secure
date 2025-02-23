"""
Test configuration and fixtures for the entire test suite.
"""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from minio import Minio
import asyncio
from typing import Generator, Any

# Add the repository root to sys.path so absolute imports work
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

# Constants for testing
TEST_USER_ID = "test_user"
TEST_FILE_ID = "test_file_123"
TEST_JOB_ID = "test_job_123"

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, Any, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_dir() -> Generator[Path, Any, None]:
    """Create a temporary directory for test files."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def mock_azure_keyvault() -> Generator[MagicMock, Any, None]:
    """Mock Azure KeyVault client."""
    # Create base64 encoded test key
    import base64
    test_key = base64.urlsafe_b64encode(b"test-key" * 4).decode()  # 32 bytes for Fernet
    
    # Create mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.return_value = {"value": test_key}
    
    # Create mock transport
    mock_transport = MagicMock()
    mock_transport.send.return_value = mock_response
    
    # Create mock pipeline
    mock_pipeline = MagicMock()
    mock_pipeline._transport = mock_transport
    
    # Create mock client with pipeline
    mock_client = MagicMock()
    mock_client._client = MagicMock(_pipeline=mock_pipeline)
    mock_client.get_secret.return_value = MagicMock(value=test_key)
    mock_client.set_secret.return_value = None
    
    # Apply all necessary patches
    with patch("azure.keyvault.secrets.SecretClient", return_value=mock_client), \
         patch("azure.core.pipeline.transport._requests_basic.RequestsTransport", return_value=mock_transport), \
         patch("azure.identity.DefaultAzureCredential", return_value=MagicMock()), \
         patch("azure.identity._credentials.environment.EnvironmentCredential", return_value=MagicMock()):
        
        yield mock_client

@pytest.fixture
def mock_minio() -> Generator[MagicMock, Any, None]:
    """Mock MinIO client."""
    mock_client = MagicMock(spec=Minio)
    
    # Mock bucket operations
    mock_client.bucket_exists.return_value = True
    mock_client.make_bucket.return_value = None
    
    # Mock object operations
    mock_client.put_object.return_value = None
    mock_client.get_object.return_value = MagicMock()
    mock_client.remove_object.return_value = None
    
    with patch("minio.Minio", return_value=mock_client):
        yield mock_client

@pytest.fixture
def test_file(temp_dir: Path) -> Generator[tuple[Path, int], Any, None]:
    """Create a test file."""
    file_path = temp_dir / "test.mp3"
    file_content = b"test audio content" * 1024  # 16KB of fake audio data
    file_path.write_bytes(file_content)
    yield file_path, len(file_content)
    if file_path.exists():
        file_path.unlink()

@pytest.fixture
def test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set up test environment variables."""
    env_vars = {
        "MINIO_HOST": "localhost",
        "MINIO_PORT": "9000",
        "MINIO_ACCESS_KEY": "test_access",
        "MINIO_SECRET_KEY": "test_secret",
        "AZURE_KEYVAULT_URL": "https://test-vault.vault.azure.net/",
        "AZURE_TENANT_ID": "test-tenant",
        "AZURE_CLIENT_ID": "test-client",
        "AZURE_CLIENT_SECRET": "test-secret",
        "MAX_UPLOAD_SIZE": "12000000000",
        "JWT_SECRET_KEY": "test-jwt-secret",
    }
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
