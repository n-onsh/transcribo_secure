"""
Tests for the file key service.

Critical aspects:
1. File key management
2. Key sharing operations
3. Access control
4. Error handling
"""
import pytest
from uuid import uuid4
from unittest.mock import MagicMock, patch
from backend.src.services.file_key_service import FileKeyService
from backend.src.models.file_key import (
    FileKey,
    FileKeyShare,
    FileKeyCreate,
    FileKeyShareCreate,
    FileKeyUpdate,
    FileKeyShareUpdate
)

@pytest.fixture
def file_key_service():
    """Create a file key service instance with mocked database."""
    with patch('backend.src.services.file_key_service.DatabaseService') as mock_db:
        service = FileKeyService()
        # Mock the database pool
        service.db.pool = MagicMock()
        yield service

@pytest.fixture
def test_file_key():
    """Create a test file key."""
    return FileKey(
        file_id=uuid4(),
        encrypted_key=b"encrypted_key_data",
        owner_id=uuid4()
    )

@pytest.fixture
def test_file_key_share():
    """Create a test file key share."""
    return FileKeyShare(
        file_id=uuid4(),
        user_id=uuid4(),
        encrypted_key=b"shared_encrypted_key_data"
    )

class TestFileKeyService:
    """Test suite for FileKeyService."""

    async def test_create_file_key(self, file_key_service, test_file_key):
        """Test file key creation."""
        # Mock database response
        file_key_service.db_service.create_file_key = MagicMock(
            return_value=test_file_key
        )

        # Create file key
        create_data = FileKeyCreate(
            file_id=test_file_key.file_id,
            encrypted_key=test_file_key.encrypted_key
        )
        result = await file_key_service.create_file_key(create_data)

        # Verify
        assert result == test_file_key
        file_key_service.db_service.create_file_key.assert_called_once_with(create_data)

    async def test_get_file_key(self, file_key_service, test_file_key):
        """Test retrieving file key."""
        # Mock database response
        file_key_service.db_service.get_file_key = MagicMock(
            return_value=test_file_key
        )

        # Get file key
        result = await file_key_service.get_file_key(test_file_key.file_id)

        # Verify
        assert result == test_file_key
        file_key_service.db_service.get_file_key.assert_called_once_with(
            test_file_key.file_id
        )

    async def test_share_file_key(self, file_key_service, test_file_key_share):
        """Test sharing file key."""
        # Mock database response
        file_key_service.db_service.create_file_key_share = MagicMock(
            return_value=test_file_key_share
        )

        # Share file key
        share_data = FileKeyShareCreate(
            file_id=test_file_key_share.file_id,
            user_id=test_file_key_share.user_id,
            encrypted_key=test_file_key_share.encrypted_key
        )
        result = await file_key_service.share_file_key(share_data)

        # Verify
        assert result == test_file_key_share
        file_key_service.db_service.create_file_key_share.assert_called_once_with(
            share_data
        )

    async def test_revoke_file_key_share(self, file_key_service, test_file_key_share):
        """Test revoking file key share."""
        # Mock database response
        file_key_service.db_service.delete_file_key_share = MagicMock(
            return_value=True
        )

        # Revoke share
        result = await file_key_service.revoke_file_key_share(
            test_file_key_share.file_id,
            test_file_key_share.user_id
        )

        # Verify
        assert result is True
        file_key_service.db_service.delete_file_key_share.assert_called_once_with(
            test_file_key_share.file_id,
            test_file_key_share.user_id
        )

    async def test_get_shared_files(self, file_key_service, test_file_key):
        """Test getting shared files."""
        user_id = uuid4()
        # Mock database response
        file_key_service.db.pool.acquire.return_value.__aenter__.return_value.fetch = MagicMock(
            return_value=[dict(test_file_key)]
        )

        # Get shared files
        result = await file_key_service.get_shared_files(user_id)

        # Verify
        assert len(result) == 1
        assert result[0].file_id == test_file_key.file_id
        assert result[0].encrypted_key == test_file_key.encrypted_key

    async def test_get_file_access(self, file_key_service, test_file_key, test_file_key_share):
        """Test getting file access information."""
        # Mock database responses
        file_key_service.get_file_key = MagicMock(return_value=test_file_key)
        file_key_service.list_file_key_shares = MagicMock(
            return_value=[test_file_key_share]
        )

        # Get file access info
        result = await file_key_service.get_file_access(test_file_key.file_id)

        # Verify
        assert result["file_id"] == test_file_key.file_id
        assert result["owner_id"] == test_file_key.owner_id
        assert test_file_key_share.user_id in result["shared_with"]

    async def test_delete_file_key(self, file_key_service, test_file_key):
        """Test deleting file key."""
        # Mock database responses
        file_key_service.db_service.delete_all_file_key_shares = MagicMock()
        file_key_service.db_service.delete_file_key = MagicMock(return_value=True)

        # Delete file key
        result = await file_key_service.delete_file_key(test_file_key.file_id)

        # Verify
        assert result is True
        file_key_service.db_service.delete_all_file_key_shares.assert_called_once_with(
            test_file_key.file_id
        )
        file_key_service.db_service.delete_file_key.assert_called_once_with(
            test_file_key.file_id
        )

    async def test_error_handling(self, file_key_service):
        """Test error handling."""
        # Mock database error
        file_key_service.db_service.get_file_key = MagicMock(
            side_effect=Exception("Database error")
        )

        # Verify error is propagated
        with pytest.raises(Exception) as exc_info:
            await file_key_service.get_file_key(uuid4())
        assert "Database error" in str(exc_info.value)

    async def test_nonexistent_file_key(self, file_key_service):
        """Test handling of nonexistent file key."""
        # Mock database response for nonexistent key
        file_key_service.db_service.get_file_key = MagicMock(return_value=None)

        # Verify None is returned
        result = await file_key_service.get_file_key(uuid4())
        assert result is None

    async def test_update_file_key(self, file_key_service, test_file_key):
        """Test updating file key."""
        # Mock database response
        file_key_service.db_service.update_file_key = MagicMock(
            return_value=test_file_key
        )

        # Update file key
        update_data = FileKeyUpdate(encrypted_key=b"new_encrypted_key")
        result = await file_key_service.update_file_key(
            test_file_key.file_id,
            update_data
        )

        # Verify
        assert result == test_file_key
        file_key_service.db_service.update_file_key.assert_called_once_with(
            test_file_key.file_id,
            update_data
        )

    async def test_update_file_key_share(self, file_key_service, test_file_key_share):
        """Test updating file key share."""
        # Mock database response
        file_key_service.db_service.update_file_key_share = MagicMock(
            return_value=test_file_key_share
        )

        # Update file key share
        update_data = FileKeyShareUpdate(encrypted_key=b"new_shared_key")
        result = await file_key_service.update_file_key_share(
            test_file_key_share.file_id,
            test_file_key_share.user_id,
            update_data
        )

        # Verify
        assert result == test_file_key_share
        file_key_service.db_service.update_file_key_share.assert_called_once_with(
            test_file_key_share.file_id,
            test_file_key_share.user_id,
            update_data
        )
