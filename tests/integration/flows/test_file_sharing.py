"""
Integration Test Suite for File Sharing Flow

This test suite verifies the complete file sharing chain including:
1. File key creation and encryption
2. Key sharing between users
3. Access control and revocation
4. Integration with Azure AD authentication

Test Flow:
1. Owner uploads file → File key created
2. Owner shares file → Key re-encrypted for recipient
3. Recipient accesses file → Key decrypted and used
4. Owner revokes access → Share removed
"""
import pytest
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from backend.src.services.file_key_service import FileKeyService
from backend.src.services.key_management import KeyManagementService
from backend.src.middleware.auth import AuthMiddleware
from backend.src.models.file_key import (
    FileKey,
    FileKeyShare,
    FileKeyCreate,
    FileKeyShareCreate
)

# Test data
TEST_FILE_ID = uuid4()
TEST_OWNER_ID = uuid4()
TEST_RECIPIENT_ID = uuid4()
TEST_FILE_KEY = b"test_file_key"
TEST_ENCRYPTED_KEY = b"encrypted_file_key"
TEST_SHARED_KEY = b"shared_file_key"

@pytest.fixture
def mock_key_service():
    """Mock key management service."""
    with patch('backend.src.services.key_management.KeyManagementService') as mock:
        service = mock.return_value
        service.derive_user_key.return_value = b"derived_user_key"
        service.encrypt_file_key.return_value = TEST_ENCRYPTED_KEY
        service.decrypt_file_key.return_value = TEST_FILE_KEY
        yield service

@pytest.fixture
def mock_auth():
    """Mock authentication middleware."""
    with patch('backend.src.middleware.auth.AuthMiddleware') as mock:
        auth = mock.return_value
        auth.get_user.return_value = {"id": TEST_OWNER_ID, "roles": ["user"]}
        yield auth

@pytest.fixture
def app(mock_key_service, mock_auth):
    """Create test FastAPI application."""
    app = FastAPI()
    app.middleware("http")(mock_auth)
    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

@pytest.fixture
def test_app(app, mock_key_service):
    """Configure test application with routes."""
    file_key_service = FileKeyService()
    
    @app.post("/files/{file_id}/share")
    async def share_file(file_id: str, recipient_id: str):
        # Create share request
        share = FileKeyShareCreate(
            file_id=file_id,
            user_id=recipient_id,
            encrypted_key=TEST_SHARED_KEY
        )
        result = await file_key_service.share_file_key(share)
        return {"status": "success", "share": result}
    
    @app.get("/files/{file_id}/key")
    async def get_file_key(file_id: str):
        result = await file_key_service.get_file_key(file_id)
        if not result:
            raise HTTPException(status_code=404, detail="File key not found")
        return result
    
    @app.delete("/files/{file_id}/share/{user_id}")
    async def revoke_access(file_id: str, user_id: str):
        result = await file_key_service.revoke_file_key_share(file_id, user_id)
        if not result:
            raise HTTPException(status_code=404, detail="Share not found")
        return {"status": "success"}
    
    return app

class TestFileSharing:
    """Test suite for file sharing flows."""

    async def test_complete_sharing_flow(self, test_app, client, mock_key_service):
        """Test complete file sharing flow from creation to revocation."""
        # 1. Create file key
        file_key = FileKeyCreate(
            file_id=TEST_FILE_ID,
            encrypted_key=TEST_ENCRYPTED_KEY
        )
        created = await FileKeyService().create_file_key(file_key)
        assert created.file_id == TEST_FILE_ID
        
        # 2. Share with recipient
        response = client.post(
            f"/files/{TEST_FILE_ID}/share",
            params={"recipient_id": str(TEST_RECIPIENT_ID)}
        )
        assert response.status_code == 200
        share_result = response.json()
        assert share_result["status"] == "success"
        
        # 3. Recipient retrieves key
        with patch('backend.src.middleware.auth.AuthMiddleware') as mock_auth:
            # Switch to recipient context
            mock_auth.return_value.get_user.return_value = {
                "id": TEST_RECIPIENT_ID,
                "roles": ["user"]
            }
            response = client.get(f"/files/{TEST_FILE_ID}/key")
            assert response.status_code == 200
            key_result = response.json()
            assert key_result["file_id"] == str(TEST_FILE_ID)
        
        # 4. Owner revokes access
        response = client.delete(
            f"/files/{TEST_FILE_ID}/share/{TEST_RECIPIENT_ID}"
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        
        # 5. Verify recipient can't access anymore
        with patch('backend.src.middleware.auth.AuthMiddleware') as mock_auth:
            mock_auth.return_value.get_user.return_value = {
                "id": TEST_RECIPIENT_ID,
                "roles": ["user"]
            }
            response = client.get(f"/files/{TEST_FILE_ID}/key")
            assert response.status_code == 404

    async def test_unauthorized_sharing(self, test_app, client, mock_key_service):
        """Test that only file owner can share."""
        # Create file key with different owner
        file_key = FileKeyCreate(
            file_id=TEST_FILE_ID,
            encrypted_key=TEST_ENCRYPTED_KEY
        )
        created = await FileKeyService().create_file_key(file_key)
        
        # Attempt to share as non-owner
        with patch('backend.src.middleware.auth.AuthMiddleware') as mock_auth:
            mock_auth.return_value.get_user.return_value = {
                "id": uuid4(),  # Different user
                "roles": ["user"]
            }
            response = client.post(
                f"/files/{TEST_FILE_ID}/share",
                params={"recipient_id": str(TEST_RECIPIENT_ID)}
            )
            assert response.status_code == 403

    async def test_share_nonexistent_file(self, test_app, client, mock_key_service):
        """Test sharing a file that doesn't exist."""
        response = client.post(
            f"/files/{uuid4()}/share",
            params={"recipient_id": str(TEST_RECIPIENT_ID)}
        )
        assert response.status_code == 404

    async def test_share_with_self(self, test_app, client, mock_key_service):
        """Test that user can't share file with themselves."""
        response = client.post(
            f"/files/{TEST_FILE_ID}/share",
            params={"recipient_id": str(TEST_OWNER_ID)}  # Same as owner
        )
        assert response.status_code == 400
        assert "Cannot share with yourself" in response.json()["detail"]

    async def test_concurrent_sharing(self, test_app, client, mock_key_service):
        """Test sharing file with multiple users concurrently."""
        import asyncio
        
        # Create file key
        file_key = FileKeyCreate(
            file_id=TEST_FILE_ID,
            encrypted_key=TEST_ENCRYPTED_KEY
        )
        created = await FileKeyService().create_file_key(file_key)
        
        # Share with multiple recipients concurrently
        async def share_with_user(user_id):
            response = client.post(
                f"/files/{TEST_FILE_ID}/share",
                params={"recipient_id": str(user_id)}
            )
            return response.status_code
        
        recipient_ids = [uuid4() for _ in range(5)]
        tasks = [share_with_user(rid) for rid in recipient_ids]
        results = await asyncio.gather(*tasks)
        
        # Verify all shares succeeded
        assert all(status == 200 for status in results)
        
        # Verify all shares exist
        access_info = await FileKeyService().get_file_access(TEST_FILE_ID)
        assert len(access_info["shared_with"]) == len(recipient_ids)

    async def test_revoke_all_shares(self, test_app, client, mock_key_service):
        """Test revoking all shares for a file."""
        # Create file key and shares
        file_key = FileKeyCreate(
            file_id=TEST_FILE_ID,
            encrypted_key=TEST_ENCRYPTED_KEY
        )
        created = await FileKeyService().create_file_key(file_key)
        
        # Share with multiple users
        recipient_ids = [uuid4() for _ in range(3)]
        for rid in recipient_ids:
            response = client.post(
                f"/files/{TEST_FILE_ID}/share",
                params={"recipient_id": str(rid)}
            )
            assert response.status_code == 200
        
        # Delete all shares
        for rid in recipient_ids:
            response = client.delete(
                f"/files/{TEST_FILE_ID}/share/{rid}"
            )
            assert response.status_code == 200
        
        # Verify no shares remain
        access_info = await FileKeyService().get_file_access(TEST_FILE_ID)
        assert len(access_info["shared_with"]) == 0

    async def test_share_after_revocation(self, test_app, client, mock_key_service):
        """Test sharing file again after revoking access."""
        # Create initial share
        file_key = FileKeyCreate(
            file_id=TEST_FILE_ID,
            encrypted_key=TEST_ENCRYPTED_KEY
        )
        created = await FileKeyService().create_file_key(file_key)
        
        # Share, revoke, then share again
        response = client.post(
            f"/files/{TEST_FILE_ID}/share",
            params={"recipient_id": str(TEST_RECIPIENT_ID)}
        )
        assert response.status_code == 200
        
        response = client.delete(
            f"/files/{TEST_FILE_ID}/share/{TEST_RECIPIENT_ID}"
        )
        assert response.status_code == 200
        
        response = client.post(
            f"/files/{TEST_FILE_ID}/share",
            params={"recipient_id": str(TEST_RECIPIENT_ID)}
        )
        assert response.status_code == 200
        
        # Verify share exists
        access_info = await FileKeyService().get_file_access(TEST_FILE_ID)
        assert TEST_RECIPIENT_ID in access_info["shared_with"]
