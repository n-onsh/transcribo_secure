"""Unit tests for storage service."""

import io
import pytest
from uuid import UUID
from unittest.mock import Mock, AsyncMock, patch
from minio.error import S3Error
from src.services.storage import StorageService
from src.utils.exceptions import StorageError, HashVerificationError

@pytest.fixture
def mock_minio():
    """Mock MinIO client."""
    return Mock()

@pytest.fixture
def mock_encryption_service():
    """Mock encryption service."""
    return Mock()

@pytest.fixture
def storage_service(mock_minio, mock_encryption_service):
    """Create storage service with mocked dependencies."""
    service = StorageService({
        'MINIO_HOST': 'localhost',
        'MINIO_PORT': '9000',
        'MINIO_ACCESS_KEY': 'test',
        'MINIO_SECRET_KEY': 'test',
        'MINIO_BUCKET': 'test',
        'MAX_FILE_SIZE': 1024 * 1024,
        'ALLOWED_EXTENSIONS': '.mp3,.wav,.m4a'
    })
    service.minio_client = mock_minio
    service.encryption_service = mock_encryption_service
    service.initialized = True
    service.bucket_name = 'test'
    return service

@pytest.mark.asyncio
async def test_store_file(storage_service, mock_minio):
    """Test storing a file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    test_data = b'test data'
    file = io.BytesIO(test_data)
    mock_minio.put_object = AsyncMock()

    # Test
    result = await storage_service.store_file(file_id, file, encrypt=False)

    # Verify
    assert result['file_id'] == str(file_id)
    assert result['size'] == len(test_data)
    assert 'hash' in result
    assert result['encrypted'] is False
    mock_minio.put_object.assert_called_once()

@pytest.mark.asyncio
async def test_store_encrypted_file(storage_service, mock_minio, mock_encryption_service):
    """Test storing an encrypted file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    test_data = b'test data'
    file = io.BytesIO(test_data)
    encrypted_data = b'encrypted data'
    mock_encryption_service.encrypt_file = AsyncMock()
    mock_minio.put_object = AsyncMock()

    # Configure mock encryption
    async def mock_encrypt(file_id, input_file, output_file):
        output_file.write(encrypted_data)
    mock_encryption_service.encrypt_file.side_effect = mock_encrypt

    # Test
    result = await storage_service.store_file(file_id, file, encrypt=True)

    # Verify
    assert result['file_id'] == str(file_id)
    assert result['size'] == len(encrypted_data)
    assert 'hash' in result
    assert result['encrypted'] is True
    mock_encryption_service.encrypt_file.assert_called_once()
    mock_minio.put_object.assert_called_once()

@pytest.mark.asyncio
async def test_get_file(storage_service, mock_minio):
    """Test retrieving a file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    test_data = b'test data'
    mock_response = Mock()
    mock_response.read = AsyncMock(return_value=test_data)
    mock_response.metadata = {'encrypted': 'false'}
    mock_minio.get_object = AsyncMock(return_value=mock_response)

    # Test
    file, metadata = await storage_service.get_file(file_id, decrypt=False)

    # Verify
    assert file.read() == test_data
    assert metadata['encrypted'] == 'false'
    mock_minio.get_object.assert_called_once()

@pytest.mark.asyncio
async def test_get_encrypted_file(storage_service, mock_minio, mock_encryption_service):
    """Test retrieving an encrypted file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    encrypted_data = b'encrypted data'
    decrypted_data = b'decrypted data'
    mock_response = Mock()
    mock_response.read = AsyncMock(return_value=encrypted_data)
    mock_response.metadata = {'encrypted': 'true'}
    mock_minio.get_object = AsyncMock(return_value=mock_response)

    # Configure mock decryption
    async def mock_decrypt(file_id, input_file, output_file):
        output_file.write(decrypted_data)
    mock_encryption_service.decrypt_file.side_effect = mock_decrypt

    # Test
    file, metadata = await storage_service.get_file(file_id, decrypt=True)

    # Verify
    assert file.read() == decrypted_data
    assert metadata['encrypted'] == 'true'
    mock_encryption_service.decrypt_file.assert_called_once()
    mock_minio.get_object.assert_called_once()

@pytest.mark.asyncio
async def test_delete_file(storage_service, mock_minio):
    """Test deleting a file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    mock_stat = Mock(size=1024)
    mock_minio.stat_object = AsyncMock(return_value=mock_stat)
    mock_minio.remove_object = AsyncMock()

    # Test
    result = await storage_service.delete_file(file_id)

    # Verify
    assert result is True
    mock_minio.stat_object.assert_called_once()
    mock_minio.remove_object.assert_called_once()

@pytest.mark.asyncio
async def test_delete_nonexistent_file(storage_service, mock_minio):
    """Test deleting a nonexistent file."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    mock_minio.stat_object = AsyncMock(side_effect=S3Error('NoSuchKey'))

    # Test
    result = await storage_service.delete_file(file_id)

    # Verify
    assert result is False
    mock_minio.stat_object.assert_called_once()
    mock_minio.remove_object.assert_not_called()

@pytest.mark.asyncio
async def test_get_file_info(storage_service, mock_minio):
    """Test getting file information."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    mock_stat = Mock(
        size=1024,
        metadata={
            'hash': 'test_hash',
            'hash_algorithm': 'sha256',
            'encrypted': 'true',
            'created_at': '2024-02-26T12:00:00Z'
        }
    )
    mock_minio.stat_object = AsyncMock(return_value=mock_stat)

    # Test
    result = await storage_service.get_file_info(file_id)

    # Verify
    assert result['file_id'] == str(file_id)
    assert result['size'] == 1024
    assert result['hash'] == 'test_hash'
    assert result['hash_algorithm'] == 'sha256'
    assert result['encrypted'] is True
    assert result['created_at'] == '2024-02-26T12:00:00Z'
    mock_minio.stat_object.assert_called_once()

@pytest.mark.asyncio
async def test_get_file_size(storage_service, mock_minio):
    """Test getting file size."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    mock_stat = Mock(size=1024)
    mock_minio.stat_object = AsyncMock(return_value=mock_stat)

    # Test
    result = await storage_service.get_file_size(file_id)

    # Verify
    assert result == 1024
    mock_minio.stat_object.assert_called_once()

@pytest.mark.asyncio
async def test_hash_verification_failure(storage_service, mock_minio):
    """Test hash verification failure."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    test_data = b'test data'
    mock_response = Mock()
    mock_response.read = AsyncMock(return_value=test_data)
    mock_response.metadata = {
        'hash': 'invalid_hash',
        'hash_algorithm': 'sha256'
    }
    mock_minio.get_object = AsyncMock(return_value=mock_response)

    # Test
    with pytest.raises(HashVerificationError):
        await storage_service.get_file(file_id)

@pytest.mark.asyncio
async def test_minio_error_handling(storage_service, mock_minio):
    """Test MinIO error handling."""
    # Setup
    file_id = UUID('12345678-1234-5678-1234-567812345678')
    mock_minio.get_object = AsyncMock(side_effect=S3Error('Test error'))

    # Test
    with pytest.raises(StorageError):
        await storage_service.get_file(file_id)

@pytest.mark.asyncio
async def test_bucket_configuration(storage_service, mock_minio):
    """Test bucket configuration."""
    # Setup
    mock_minio.bucket_exists = AsyncMock(return_value=False)
    mock_minio.make_bucket = AsyncMock()
    mock_minio.set_bucket_versioning = AsyncMock()
    mock_minio.set_bucket_lifecycle = AsyncMock()
    mock_minio.set_bucket_encryption = AsyncMock()

    # Test
    await storage_service._ensure_bucket_exists()

    # Verify
    mock_minio.bucket_exists.assert_called_once()
    mock_minio.make_bucket.assert_called_once()
    mock_minio.set_bucket_versioning.assert_called_once()
    mock_minio.set_bucket_lifecycle.assert_called_once()
    mock_minio.set_bucket_encryption.assert_called_once()
