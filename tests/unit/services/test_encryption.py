"""Tests for encryption service."""

import io
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from uuid import UUID

from backend.src.services.encryption import EncryptionService
from backend.src.services.file_key_service import FileKeyService
from backend.src.utils.exceptions import EncryptionError

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "storage": {
            "encryption": {
                "enabled": True,
                "algorithm": "AES-256-GCM",
                "key_rotation_days": 30,
                "chunk_size_mb": 1  # Small chunk size for testing
            }
        }
    }

@pytest.fixture
def mock_key_service():
    """Mock file key service."""
    service = Mock(spec=FileKeyService)
    service.initialized = True
    service.get_key = AsyncMock(return_value=os.urandom(32))  # Random 256-bit key
    service.generate_key = AsyncMock(return_value=os.urandom(32))
    service.rotate_key = AsyncMock(return_value=os.urandom(32))
    return service

@pytest.fixture
def service(mock_config):
    """Create encryption service."""
    with patch("backend.src.services.encryption.config", mock_config):
        return EncryptionService({})

@pytest.fixture
def file_id():
    """Create test file ID."""
    return UUID("12345678-1234-5678-1234-567812345678")

@pytest.mark.asyncio
async def test_initialization(service, mock_key_service):
    """Test service initialization."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        
        await service.initialize()
        
        assert service.key_service == mock_key_service
        assert service.chunk_size == 1024 * 1024  # 1MB

@pytest.mark.asyncio
async def test_initialization_disabled(mock_config, service):
    """Test initialization when encryption is disabled."""
    mock_config["storage"]["encryption"]["enabled"] = False
    
    with patch("backend.src.services.encryption.config", mock_config):
        await service.initialize()
        assert not service.initialized

@pytest.mark.asyncio
async def test_encrypt_file(service, mock_key_service, file_id):
    """Test file encryption."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Create test data
        data = b"test data" * 1000  # ~9KB of data
        input_file = io.BytesIO(data)
        output_file = io.BytesIO()
        
        # Encrypt
        await service.encrypt_file(file_id, input_file, output_file)
        
        # Verify
        encrypted_data = output_file.getvalue()
        assert len(encrypted_data) > len(data)  # Should include IV and tag
        assert encrypted_data != data  # Should be encrypted
        assert encrypted_data[:12]  # Should have IV
        assert encrypted_data[-16:]  # Should have authentication tag

@pytest.mark.asyncio
async def test_decrypt_file(service, mock_key_service, file_id):
    """Test file decryption."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Create and encrypt test data
        data = b"test data" * 1000
        input_file = io.BytesIO(data)
        encrypted_file = io.BytesIO()
        await service.encrypt_file(file_id, input_file, encrypted_file)
        
        # Decrypt
        encrypted_file.seek(0)
        output_file = io.BytesIO()
        await service.decrypt_file(file_id, encrypted_file, output_file)
        
        # Verify
        decrypted_data = output_file.getvalue()
        assert decrypted_data == data

@pytest.mark.asyncio
async def test_decrypt_invalid_format(service, mock_key_service, file_id):
    """Test decryption with invalid format."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Try to decrypt invalid data
        input_file = io.BytesIO(b"invalid data")
        output_file = io.BytesIO()
        
        with pytest.raises(EncryptionError) as exc:
            await service.decrypt_file(file_id, input_file, output_file)
        assert "Invalid encrypted file format" in str(exc.value)

@pytest.mark.asyncio
async def test_decrypt_tampered_data(service, mock_key_service, file_id):
    """Test decryption with tampered data."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Create and encrypt test data
        data = b"test data" * 1000
        input_file = io.BytesIO(data)
        encrypted_file = io.BytesIO()
        await service.encrypt_file(file_id, input_file, encrypted_file)
        
        # Tamper with encrypted data
        encrypted_data = bytearray(encrypted_file.getvalue())
        encrypted_data[20] ^= 0x01  # Flip a bit
        tampered_file = io.BytesIO(encrypted_data)
        
        # Try to decrypt
        output_file = io.BytesIO()
        with pytest.raises(EncryptionError):
            await service.decrypt_file(file_id, tampered_file, output_file)

@pytest.mark.asyncio
async def test_rotate_file_key(service, mock_key_service, file_id):
    """Test key rotation."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Create and encrypt test data
        data = b"test data" * 1000
        input_file = io.BytesIO(data)
        encrypted_file = io.BytesIO()
        await service.encrypt_file(file_id, input_file, encrypted_file)
        
        # Rotate key
        encrypted_file.seek(0)
        output_file = io.BytesIO()
        await service.rotate_file_key(file_id, encrypted_file, output_file)
        
        # Verify
        output_file.seek(0)
        decrypted_file = io.BytesIO()
        await service.decrypt_file(file_id, output_file, decrypted_file)
        assert decrypted_file.getvalue() == data

@pytest.mark.asyncio
async def test_large_file_handling(service, mock_key_service, file_id):
    """Test handling of large files."""
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        # Create large test data (5MB)
        data = os.urandom(5 * 1024 * 1024)
        input_file = io.BytesIO(data)
        encrypted_file = io.BytesIO()
        
        # Encrypt
        await service.encrypt_file(file_id, input_file, encrypted_file)
        
        # Decrypt
        encrypted_file.seek(0)
        output_file = io.BytesIO()
        await service.decrypt_file(file_id, encrypted_file, output_file)
        
        # Verify
        assert output_file.getvalue() == data

@pytest.mark.asyncio
async def test_error_handling(service, mock_key_service, file_id):
    """Test error handling."""
    mock_key_service.get_key.side_effect = Exception("Test error")
    
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        input_file = io.BytesIO(b"test data")
        output_file = io.BytesIO()
        
        with pytest.raises(EncryptionError) as exc:
            await service.encrypt_file(file_id, input_file, output_file)
        assert "Failed to encrypt file" in str(exc.value)
        assert "Test error" in str(exc.value)

@pytest.mark.asyncio
async def test_key_not_found(service, mock_key_service, file_id):
    """Test decryption with missing key."""
    mock_key_service.get_key.return_value = None
    
    with patch("backend.src.services.encryption.service_provider") as mock_provider:
        mock_provider.get.return_value = mock_key_service
        await service.initialize()
        
        input_file = io.BytesIO(b"test data")
        output_file = io.BytesIO()
        
        with pytest.raises(EncryptionError) as exc:
            await service.decrypt_file(file_id, input_file, output_file)
        assert "No key found for file" in str(exc.value)
