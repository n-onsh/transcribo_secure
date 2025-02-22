"""
Tests for the storage service.

Critical aspects:
1. File operations with encryption
2. Bucket management
3. Error handling
4. Security boundaries
"""
import pytest
from pathlib import Path
import os
from unittest.mock import MagicMock, patch
from backend.src.services.storage import StorageService

@pytest.fixture
def storage_service(mock_minio, test_env) -> StorageService:
    """Create a storage service instance with mocked MinIO."""
    return StorageService()

class TestStorageService:
    """Test suite for StorageService."""

    async def test_initialization(self, mock_minio, test_env):
        """Test service initialization and bucket setup."""
        service = StorageService()
        await service._init_buckets()

        # Verify all required buckets are created
        for bucket_config in service.buckets.values():
            mock_minio.bucket_exists.assert_any_call(bucket_config["name"])

    async def test_store_file(self, storage_service, test_file):
        """Test file storage with validation."""
        file_path, file_size = test_file
        test_data = file_path.read_bytes()
        
        # Store file in audio bucket
        await storage_service.store_file(
            user_id="test_user",
            data=test_data,
            file_name="test.mp3",
            bucket_type="audio"
        )

        # Verify MinIO operations
        storage_service.client.put_object.assert_called_once()
        call_args = storage_service.client.put_object.call_args
        assert call_args is not None
        assert call_args[0][0] == "audio"  # bucket name
        assert "test_user/test.mp3" in call_args[0][1]  # object path

    async def test_retrieve_file(self, storage_service, test_file):
        """Test file retrieval."""
        file_path, _ = test_file
        test_data = file_path.read_bytes()
        
        # Mock get_object to return our test data
        mock_response = MagicMock()
        mock_response.read.return_value = test_data
        storage_service.client.get_object.return_value = mock_response

        # Retrieve file
        retrieved_data = await storage_service.retrieve_file(
            user_id="test_user",
            file_name="test.mp3",
            bucket_type="audio"
        )

        assert retrieved_data == test_data
        storage_service.client.get_object.assert_called_once()

    @pytest.mark.parametrize("bucket_type,file_name,should_pass", [
        ("audio", "test.mp3", True),
        ("audio", "test.wav", True),
        ("audio", "test.txt", False),
        ("transcription", "test.json", True),
        ("transcription", "test.mp3", False),
    ])
    async def test_file_validation(self, storage_service, test_file, bucket_type, file_name, should_pass):
        """Test file validation for different bucket types."""
        file_path, _ = test_file
        test_data = file_path.read_bytes()

        if should_pass:
            # Should succeed
            await storage_service.store_file(
                user_id="test_user",
                data=test_data,
                file_name=file_name,
                bucket_type=bucket_type
            )
            storage_service.client.put_object.assert_called_once()
        else:
            # Should raise validation error
            with pytest.raises(ValueError):
                await storage_service.store_file(
                    user_id="test_user",
                    data=test_data,
                    file_name=file_name,
                    bucket_type=bucket_type
                )

    async def test_file_size_limits(self, storage_service):
        """Test file size validation."""
        # Create oversized test data
        oversized_data = b"x" * (500 * 1024 * 1024 + 1)  # Exceeds 500MB limit for audio

        with pytest.raises(ValueError) as exc_info:
            await storage_service.store_file(
                user_id="test_user",
                data=oversized_data,
                file_name="large.mp3",
                bucket_type="audio"
            )
        assert "too large" in str(exc_info.value)

    async def test_delete_file(self, storage_service):
        """Test file deletion."""
        await storage_service.delete_file(
            user_id="test_user",
            file_name="test.mp3",
            bucket_type="audio"
        )

        storage_service.client.remove_object.assert_called_once_with(
            "audio",
            "test_user/test.mp3"
        )

    async def test_list_files(self, storage_service):
        """Test file listing."""
        # Mock list_objects response
        mock_obj1 = MagicMock(object_name="test_user/file1.mp3", size=1024)
        mock_obj2 = MagicMock(object_name="test_user/file2.mp3", size=2048)
        storage_service.client.list_objects.return_value = [mock_obj1, mock_obj2]

        files = await storage_service.list_files(
            user_id="test_user",
            bucket_type="audio"
        )

        assert len(files) == 2
        assert files[0]["name"] == "file1.mp3"
        assert files[1]["name"] == "file2.mp3"

    async def test_cleanup_temp_files(self, storage_service):
        """Test temporary file cleanup."""
        # Mock list_objects to return some old files
        mock_old_file = MagicMock(
            object_name="old_file.tmp",
            last_modified="2024-01-01T00:00:00Z"
        )
        storage_service.client.list_objects.return_value = [mock_old_file]

        await storage_service.cleanup_temp_files(max_age=1)
        storage_service.client.remove_object.assert_called_once()

    async def test_error_handling(self, storage_service):
        """Test error handling for storage operations."""
        # Test non-existent bucket
        with pytest.raises(ValueError):
            await storage_service.store_file(
                user_id="test_user",
                data=b"test",
                file_name="test.mp3",
                bucket_type="nonexistent"
            )

        # Test MinIO errors
        storage_service.client.put_object.side_effect = Exception("Storage error")
        with pytest.raises(Exception):
            await storage_service.store_file(
                user_id="test_user",
                data=b"test",
                file_name="test.mp3",
                bucket_type="audio"
            )

    async def test_bucket_size_metrics(self, storage_service):
        """Test bucket size calculation."""
        # Mock list_objects to return files with known sizes
        mock_files = [
            MagicMock(size=1024),  # 1KB
            MagicMock(size=2048),  # 2KB
        ]
        storage_service.client.list_objects.return_value = mock_files

        size = await storage_service.get_bucket_size("audio")
        assert size == 3072  # 3KB total
