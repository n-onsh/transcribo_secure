import io
import pytest
import os
from backend_api.src.services.storage import StorageService
from backend_api.src.services.encryption import EncryptionService

# Create a dummy encryption service for testing purposes.
class DummyEncryptionService:
    async def encrypt_data(self, data):
        # Simple dummy "encryption": reverse the bytes.
        return data[::-1]

    async def decrypt_data(self, encrypted_data):
        # "Decryption": reverse again.
        return encrypted_data[::-1]

@pytest.fixture
def storage_service(monkeypatch):
    # Override the Minio host to "localhost" for testing.
    monkeypatch.setenv("MINIO_HOST", "localhost")
    monkeypatch.setenv("MINIO_PORT", "9000")
    service = StorageService()
    # Override the encryption service with the dummy implementation.
    service.encryption = DummyEncryptionService()
    return service

@pytest.mark.asyncio
async def test_store_and_retrieve_file(storage_service):
    # Set up dummy file metadata.
    file_id = "123e4567-e89b-12d3-a456-426614174000"
    file_name = "dummy.txt"
    file_type = "input"
    file_content = io.BytesIO(b"Hello, world!")
    
    # Test storing the file.
    total_size = await storage_service.store_file(
        file_id=file_id,
        file_data=file_content,
        file_name=file_name,
        file_type=file_type,
        metadata={"dummy": "data"}
    )
    # Check that the total size is equal to the length of the content.
    assert total_size == len(b"Hello, world!")
    
    # Test the dummy encryption and decryption round-trip.
    encrypted = await storage_service.encryption.encrypt_data(b"TestData")
    decrypted = await storage_service.encryption.decrypt_data(encrypted)
    assert decrypted == b"TestData"
