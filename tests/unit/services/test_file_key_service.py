"""Tests for file key service."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from uuid import UUID

from backend.src.services.file_key_service import FileKeyService
from backend.src.services.keyvault import KeyVaultService
from backend.src.services.database import DatabaseService
from backend.src.utils.exceptions import KeyManagementError

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "storage": {
            "encryption": {
                "enabled": True,
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "chunk_size_mb": 5
            }
        }
    }

@pytest.fixture
def mock_key_vault():
    """Mock Key Vault service."""
    service = Mock(spec=KeyVaultService)
    service.initialized = True
    service.get_secret = AsyncMock(return_value="dGVzdC1rZXk=")  # base64 encoded "test-key"
    service.set_secret = AsyncMock()
    service.delete_secret = AsyncMock()
    return service

@pytest.fixture
def mock_db():
    """Mock database service."""
    service = Mock(spec=DatabaseService)
    service.initialized = True
    service.execute = AsyncMock()
    service.fetch_one = AsyncMock()
    service.fetch_all = AsyncMock()
    service.transaction = AsyncMock()
    return service

@pytest.fixture
def service(mock_config):
    """Create file key service."""
    with patch("backend.src.services.file_key_service.config", mock_config):
        return FileKeyService({})

@pytest.fixture
def file_id():
    """Create test file ID."""
    return UUID("12345678-1234-5678-1234-567812345678")

@pytest.mark.asyncio
async def test_initialization(service, mock_key_vault, mock_db):
    """Test service initialization."""
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        
        await service.initialize()
        
        assert service.key_vault == mock_key_vault
        assert service.db == mock_db
        mock_db.execute.assert_called()  # Should create table

@pytest.mark.asyncio
async def test_initialization_disabled(mock_config, service):
    """Test initialization when encryption is disabled."""
    mock_config["storage"]["encryption"]["enabled"] = False
    
    with patch("backend.src.services.file_key_service.config", mock_config):
        await service.initialize()
        assert not service.initialized

@pytest.mark.asyncio
async def test_generate_key(service, mock_key_vault, mock_db, file_id):
    """Test key generation."""
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        key = await service.generate_key(file_id)
        
        assert len(key) == 32  # 256 bits
        mock_key_vault.set_secret.assert_called_once()
        mock_db.execute.assert_called()  # Should insert key metadata

@pytest.mark.asyncio
async def test_get_key(service, mock_key_vault, mock_db, file_id):
    """Test key retrieval."""
    mock_db.fetch_one.return_value = {"key_reference": f"file-{file_id}"}
    
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        key = await service.get_key(file_id)
        
        assert key == b"test-key"  # Decoded from base64
        mock_key_vault.get_secret.assert_called_once_with(f"file-{file_id}")

@pytest.mark.asyncio
async def test_get_key_not_found(service, mock_key_vault, mock_db, file_id):
    """Test getting nonexistent key."""
    mock_db.fetch_one.return_value = None
    
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        key = await service.get_key(file_id)
        assert key is None

@pytest.mark.asyncio
async def test_rotate_key(service, mock_key_vault, mock_db, file_id):
    """Test key rotation."""
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        new_key = await service.rotate_key(file_id)
        
        assert len(new_key) == 32  # 256 bits
        mock_key_vault.set_secret.assert_called_once()
        assert mock_db.execute.call_count >= 2  # Insert new key + update old key

@pytest.mark.asyncio
async def test_cleanup_expired_keys(service, mock_key_vault, mock_db):
    """Test expired key cleanup."""
    mock_db.fetch_all.return_value = [
        {"key_reference": "key1"},
        {"key_reference": "key2"}
    ]
    
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        await service.cleanup_expired_keys()
        
        assert mock_key_vault.delete_secret.call_count == 2
        mock_db.execute.assert_called()  # Should delete expired keys

def test_derive_key(service):
    """Test key derivation."""
    master_key = b"master-key"
    salt = b"salt"
    info = b"info"
    
    key = service.derive_key(master_key, salt, info)
    
    assert len(key) == 32  # 256 bits
    assert key != master_key  # Should be derived

@pytest.mark.asyncio
async def test_error_handling(service, mock_key_vault, mock_db, file_id):
    """Test error handling."""
    mock_key_vault.get_secret.side_effect = Exception("Test error")
    
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        with pytest.raises(KeyManagementError) as exc:
            await service.get_key(file_id)
        
        assert "Failed to get key" in str(exc.value)
        assert "Test error" in str(exc.value)

@pytest.mark.asyncio
async def test_lazy_key_rotation(service, mock_key_vault, mock_db, file_id):
    """Test lazy key rotation."""
    # Set up expired key
    mock_db.fetch_one.return_value = {
        "key_reference": f"file-{file_id}",
        "created_at": datetime.utcnow() - timedelta(days=31)
    }
    
    with patch("backend.src.services.file_key_service.service_provider") as mock_provider:
        mock_provider.get.side_effect = [mock_key_vault, mock_db]
        await service.initialize()
        
        # Getting key should trigger rotation
        key = await service.get_key(file_id)
        assert key is not None
        assert mock_key_vault.set_secret.called  # Should create new key
        assert mock_db.execute.called  # Should update key metadata
