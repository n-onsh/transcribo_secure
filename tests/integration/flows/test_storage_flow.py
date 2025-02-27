"""Integration tests for storage flow."""

import io
import os
import uuid
import pytest
from typing import Dict, Any
from src.services.storage import StorageService
from src.services.encryption import EncryptionService
from src.services.file_key_service import FileKeyService
from src.services.keyvault import KeyVaultService
from src.utils.exceptions import StorageError, HashVerificationError

@pytest.fixture
async def settings() -> Dict[str, Any]:
    """Get test settings."""
    return {
        'MINIO_HOST': os.getenv('MINIO_HOST', 'localhost'),
        'MINIO_PORT': os.getenv('MINIO_PORT', '9000'),
        'MINIO_ACCESS_KEY': os.getenv('MINIO_ACCESS_KEY', 'test'),
        'MINIO_SECRET_KEY': os.getenv('MINIO_SECRET_KEY', 'test'),
        'MINIO_BUCKET': 'test-bucket',
        'MAX_FILE_SIZE': 1024 * 1024,
        'ALLOWED_EXTENSIONS': '.mp3,.wav,.m4a',
        'AZURE_KEYVAULT_URL': os.getenv('AZURE_KEYVAULT_URL'),
        'AZURE_TENANT_ID': os.getenv('AZURE_TENANT_ID'),
        'AZURE_CLIENT_ID': os.getenv('AZURE_CLIENT_ID'),
        'AZURE_CLIENT_SECRET': os.getenv('AZURE_CLIENT_SECRET'),
        'KEY_VAULT_CACHE_ENABLED': True,
        'KEY_VAULT_CACHE_MINUTES': 5,
        'KEY_ROTATION_INTERVAL_DAYS': 30,
        'MIN_KEY_LENGTH': 32,
        'ENCRYPTION_CHUNK_SIZE_MB': 1
    }

@pytest.fixture
async def key_vault_service(settings: Dict[str, Any]) -> KeyVaultService:
    """Create key vault service."""
    service = KeyVaultService(settings)
    await service.initialize()
    return service

@pytest.fixture
async def file_key_service(settings: Dict[str, Any], key_vault_service: KeyVaultService) -> FileKeyService:
    """Create file key service."""
    service = FileKeyService(settings)
    await service.initialize()
    return service

@pytest.fixture
async def encryption_service(settings: Dict[str, Any], file_key_service: FileKeyService) -> EncryptionService:
    """Create encryption service."""
    service = EncryptionService(settings)
    await service.initialize()
    return service

@pytest.fixture
async def storage_service(settings: Dict[str, Any], encryption_service: EncryptionService) -> StorageService:
    """Create storage service."""
    service = StorageService(settings)
    await service.initialize()
    return service

@pytest.mark.asyncio
async def test_store_and_retrieve_file(storage_service: StorageService):
    """Test storing and retrieving a file."""
    # Setup
    file_id = uuid.uuid4()
    test_data = b'test data'
    file = io.BytesIO(test_data)
    metadata = {'content_type': 'text/plain'}

    try:
        # Store file
        result = await storage_service.store_file(
            file_id=file_id,
            file=file,
            metadata=metadata,
            encrypt=False
        )

        # Verify store result
        assert result['file_id'] == str(file_id)
        assert result['size'] == len(test_data)
        assert result['encrypted'] is False
        assert 'hash' in result

        # Get file info
        info = await storage_service.get_file_info(file_id)
        assert info is not None
        assert info['file_id'] == str(file_id)
        assert info['size'] == len(test_data)
        assert info['encrypted'] is False

        # Get file
        retrieved_file, retrieved_metadata = await storage_service.get_file(
            file_id=file_id,
            decrypt=False
        )

        # Verify retrieved file
        assert retrieved_file.read() == test_data
        assert retrieved_metadata['content_type'] == 'text/plain'

    finally:
        # Cleanup
        await storage_service.delete_file(file_id)

@pytest.mark.asyncio
async def test_store_and_retrieve_encrypted_file(storage_service: StorageService):
    """Test storing and retrieving an encrypted file."""
    # Setup
    file_id = uuid.uuid4()
    test_data = b'test data'
    file = io.BytesIO(test_data)
    metadata = {'content_type': 'text/plain'}

    try:
        # Store encrypted file
        result = await storage_service.store_file(
            file_id=file_id,
            file=file,
            metadata=metadata,
            encrypt=True
        )

        # Verify store result
        assert result['file_id'] == str(file_id)
        assert result['encrypted'] is True
        assert 'hash' in result

        # Get file info
        info = await storage_service.get_file_info(file_id)
        assert info is not None
        assert info['file_id'] == str(file_id)
        assert info['encrypted'] is True

        # Get decrypted file
        retrieved_file, retrieved_metadata = await storage_service.get_file(
            file_id=file_id,
            decrypt=True
        )

        # Verify decrypted file
        assert retrieved_file.read() == test_data
        assert retrieved_metadata['content_type'] == 'text/plain'

        # Get encrypted file
        encrypted_file, encrypted_metadata = await storage_service.get_file(
            file_id=file_id,
            decrypt=False
        )

        # Verify encrypted file is different
        assert encrypted_file.read() != test_data
        assert encrypted_metadata['encrypted'] == 'true'

    finally:
        # Cleanup
        await storage_service.delete_file(file_id)

@pytest.mark.asyncio
async def test_file_not_found(storage_service: StorageService):
    """Test handling of nonexistent files."""
    file_id = uuid.uuid4()

    # Get file info
    info = await storage_service.get_file_info(file_id)
    assert info is None

    # Get file
    file, metadata = await storage_service.get_file(file_id)
    assert file is None
    assert metadata == {}

    # Delete file
    result = await storage_service.delete_file(file_id)
    assert result is False

@pytest.mark.asyncio
async def test_large_file_handling(storage_service: StorageService):
    """Test handling of large files with streaming."""
    # Setup
    file_id = uuid.uuid4()
    large_data = os.urandom(5 * 1024 * 1024)  # 5MB
    file = io.BytesIO(large_data)
    metadata = {'content_type': 'application/octet-stream'}

    try:
        # Store large file
        result = await storage_service.store_file(
            file_id=file_id,
            file=file,
            metadata=metadata,
            encrypt=True
        )

        # Verify store result
        assert result['file_id'] == str(file_id)
        assert result['size'] > len(large_data)  # Size includes encryption overhead
        assert result['encrypted'] is True

        # Get decrypted file
        retrieved_file, _ = await storage_service.get_file(
            file_id=file_id,
            decrypt=True
        )

        # Verify decrypted file
        assert retrieved_file.read() == large_data

    finally:
        # Cleanup
        await storage_service.delete_file(file_id)

@pytest.mark.asyncio
async def test_hash_verification(storage_service: StorageService):
    """Test hash verification during file operations."""
    # Setup
    file_id = uuid.uuid4()
    test_data = b'test data'
    file = io.BytesIO(test_data)

    try:
        # Store file
        result = await storage_service.store_file(
            file_id=file_id,
            file=file,
            encrypt=False
        )

        # Verify hash is present
        assert 'hash' in result
        assert result['hash_algorithm'] == 'sha256'

        # Corrupt the file's stored hash
        info = await storage_service.get_file_info(file_id)
        corrupted_metadata = info['metadata']
        corrupted_metadata['hash'] = 'invalid_hash'

        # Attempt to get file with invalid hash
        with pytest.raises(HashVerificationError):
            await storage_service.get_file(file_id)

    finally:
        # Cleanup
        await storage_service.delete_file(file_id)

@pytest.mark.asyncio
async def test_concurrent_access(storage_service: StorageService):
    """Test concurrent access to storage service."""
    file_ids = [uuid.uuid4() for _ in range(5)]
    test_data = b'test data'
    files = [(id, io.BytesIO(test_data)) for id in file_ids]

    try:
        # Store files concurrently
        store_tasks = [
            storage_service.store_file(
                file_id=file_id,
                file=file,
                encrypt=True
            )
            for file_id, file in files
        ]
        store_results = await asyncio.gather(*store_tasks)

        # Verify all files stored successfully
        assert len(store_results) == len(files)
        for result in store_results:
            assert result['encrypted'] is True

        # Retrieve files concurrently
        get_tasks = [
            storage_service.get_file(file_id)
            for file_id, _ in files
        ]
        get_results = await asyncio.gather(*get_tasks)

        # Verify all files retrieved successfully
        for file, _ in get_results:
            assert file.read() == test_data

    finally:
        # Cleanup
        delete_tasks = [
            storage_service.delete_file(file_id)
            for file_id, _ in files
        ]
        await asyncio.gather(*delete_tasks)
