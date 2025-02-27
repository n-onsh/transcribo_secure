"""Integration tests for encryption flow."""

import os
import io
import pytest
from uuid import UUID
from datetime import datetime, timedelta

from backend.src.services.keyvault import KeyVaultService
from backend.src.services.file_key_service import FileKeyService
from backend.src.services.encryption import EncryptionService
from backend.src.services.database import DatabaseService
from backend.src.utils.exceptions import EncryptionError

@pytest.fixture
async def key_vault_service():
    """Create Key Vault service."""
    service = KeyVaultService({})
    await service.initialize()
    return service

@pytest.fixture
async def database_service():
    """Create database service."""
    service = DatabaseService({})
    await service.initialize()
    
    # Create test table
    await service.execute("""
        CREATE TABLE IF NOT EXISTS file_keys (
            id SERIAL PRIMARY KEY,
            file_id UUID NOT NULL,
            key_reference TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP WITH TIME ZONE,
            UNIQUE(file_id, key_reference)
        )
    """)
    
    yield service
    
    # Cleanup
    await service.execute("DROP TABLE IF EXISTS file_keys")

@pytest.fixture
async def file_key_service(key_vault_service, database_service):
    """Create file key service."""
    service = FileKeyService({})
    await service.initialize()
    return service

@pytest.fixture
async def encryption_service(file_key_service):
    """Create encryption service."""
    service = EncryptionService({})
    await service.initialize()
    return service

@pytest.fixture
def file_id():
    """Create test file ID."""
    return UUID("12345678-1234-5678-1234-567812345678")

@pytest.mark.asyncio
async def test_complete_encryption_flow(
    encryption_service,
    file_key_service,
    key_vault_service,
    database_service,
    file_id
):
    """Test complete encryption flow."""
    # Create test data
    data = b"test data" * 1000  # ~9KB
    input_file = io.BytesIO(data)
    encrypted_file = io.BytesIO()
    
    # Encrypt file
    await encryption_service.encrypt_file(file_id, input_file, encrypted_file)
    
    # Verify encrypted data
    encrypted_data = encrypted_file.getvalue()
    assert len(encrypted_data) > len(data)  # Should include IV and tag
    assert encrypted_data != data  # Should be encrypted
    
    # Verify key in Key Vault
    key_name = f"file-{file_id}"
    key = await key_vault_service.get_secret(key_name)
    assert key is not None
    
    # Verify key metadata in database
    result = await database_service.fetch_one(
        "SELECT * FROM file_keys WHERE file_id = $1",
        str(file_id)
    )
    assert result is not None
    assert result["key_reference"] == key_name
    
    # Decrypt file
    encrypted_file.seek(0)
    decrypted_file = io.BytesIO()
    await encryption_service.decrypt_file(file_id, encrypted_file, decrypted_file)
    
    # Verify decrypted data
    assert decrypted_file.getvalue() == data

@pytest.mark.asyncio
async def test_key_rotation_flow(
    encryption_service,
    file_key_service,
    key_vault_service,
    database_service,
    file_id
):
    """Test key rotation flow."""
    # Create and encrypt test data
    data = b"test data" * 1000
    input_file = io.BytesIO(data)
    encrypted_file = io.BytesIO()
    await encryption_service.encrypt_file(file_id, input_file, encrypted_file)
    
    # Get original key info
    original_key = await key_vault_service.get_secret(f"file-{file_id}")
    original_metadata = await database_service.fetch_one(
        "SELECT * FROM file_keys WHERE file_id = $1",
        str(file_id)
    )
    
    # Rotate key
    encrypted_file.seek(0)
    rotated_file = io.BytesIO()
    await encryption_service.rotate_file_key(file_id, encrypted_file, rotated_file)
    
    # Verify new key in Key Vault
    new_key = await key_vault_service.get_secret(f"file-{file_id}")
    assert new_key != original_key
    
    # Verify key metadata updated
    new_metadata = await database_service.fetch_one(
        "SELECT * FROM file_keys WHERE file_id = $1 AND expires_at IS NULL",
        str(file_id)
    )
    assert new_metadata["id"] != original_metadata["id"]
    
    # Verify original key marked as expired
    expired_metadata = await database_service.fetch_one(
        "SELECT * FROM file_keys WHERE id = $1",
        original_metadata["id"]
    )
    assert expired_metadata["expires_at"] is not None
    
    # Verify decryption with new key
    rotated_file.seek(0)
    decrypted_file = io.BytesIO()
    await encryption_service.decrypt_file(file_id, rotated_file, decrypted_file)
    assert decrypted_file.getvalue() == data

@pytest.mark.asyncio
async def test_key_cleanup_flow(
    encryption_service,
    file_key_service,
    key_vault_service,
    database_service,
    file_id
):
    """Test expired key cleanup flow."""
    # Create test data and encrypt
    data = b"test data" * 1000
    input_file = io.BytesIO(data)
    encrypted_file = io.BytesIO()
    await encryption_service.encrypt_file(file_id, input_file, encrypted_file)
    
    # Set key as expired
    await database_service.execute(
        """
        UPDATE file_keys 
        SET expires_at = $1 
        WHERE file_id = $2
        """,
        datetime.utcnow() - timedelta(days=1),
        str(file_id)
    )
    
    # Run cleanup
    await file_key_service.cleanup_expired_keys()
    
    # Verify key removed from Key Vault
    key = await key_vault_service.get_secret(f"file-{file_id}")
    assert key is None
    
    # Verify key metadata removed from database
    result = await database_service.fetch_one(
        "SELECT * FROM file_keys WHERE file_id = $1",
        str(file_id)
    )
    assert result is None
    
    # Verify decryption fails
    encrypted_file.seek(0)
    decrypted_file = io.BytesIO()
    with pytest.raises(EncryptionError) as exc:
        await encryption_service.decrypt_file(file_id, encrypted_file, decrypted_file)
    assert "No key found for file" in str(exc.value)

@pytest.mark.asyncio
async def test_tamper_detection(
    encryption_service,
    file_key_service,
    file_id
):
    """Test encrypted data tamper detection."""
    # Create and encrypt test data
    data = b"test data" * 1000
    input_file = io.BytesIO(data)
    encrypted_file = io.BytesIO()
    await encryption_service.encrypt_file(file_id, input_file, encrypted_file)
    
    # Tamper with encrypted data
    encrypted_data = bytearray(encrypted_file.getvalue())
    encrypted_data[20] ^= 0x01  # Flip a bit
    tampered_file = io.BytesIO(encrypted_data)
    
    # Verify decryption fails
    decrypted_file = io.BytesIO()
    with pytest.raises(EncryptionError):
        await encryption_service.decrypt_file(file_id, tampered_file, decrypted_file)

@pytest.mark.asyncio
async def test_large_file_handling(
    encryption_service,
    file_key_service,
    file_id
):
    """Test handling of large files."""
    # Create large test data (10MB)
    data = os.urandom(10 * 1024 * 1024)
    input_file = io.BytesIO(data)
    encrypted_file = io.BytesIO()
    
    # Encrypt
    await encryption_service.encrypt_file(file_id, input_file, encrypted_file)
    
    # Decrypt
    encrypted_file.seek(0)
    decrypted_file = io.BytesIO()
    await encryption_service.decrypt_file(file_id, encrypted_file, decrypted_file)
    
    # Verify
    assert decrypted_file.getvalue() == data
