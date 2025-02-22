"""
End-to-End Test Suite for Critical User Flows

This test suite verifies critical user workflows in a real environment,
focusing on file upload and processing scenarios that involve multiple
system components working together.

Test Categories:
1. File Upload Flows
   - Valid file uploads
   - Invalid file rejections
   - Large file handling
   - Concurrent uploads

2. Security Boundaries
   - Authentication requirements
   - Authorization checks
   - File access controls
   - Error handling

3. Performance Validation
   - Upload response times
   - Processing throughput
   - Resource usage
"""
import pytest
import asyncio
import time
from fastapi.testclient import TestClient
from backend.src.main import app
from backend.src.services.storage import StorageService
from backend.src.services.encryption import EncryptionService

# Test data
VALID_MP3_CONTENT = b"ID3" + b"\x00" * 1024
VALID_WAV_CONTENT = b"RIFF" + b"\x00" * 1024
LARGE_CONTENT = b"\x00" * (10 * 1024 * 1024)  # 10MB

@pytest.fixture(scope="module")
def client():
    """Create test client with real services."""
    return TestClient(app)

@pytest.fixture(scope="module")
async def storage():
    """Initialize real storage service."""
    service = StorageService()
    await service.initialize()
    yield service
    await service.cleanup()

@pytest.fixture(scope="module")
async def encryption():
    """Initialize real encryption service."""
    service = EncryptionService()
    await service.initialize()
    yield service
    await service.cleanup()

class TestCriticalUserFlows:
    """Test suite for end-to-end user workflows."""

    async def test_valid_file_upload_flow(self, client):
        """Test complete flow for valid file upload."""
        # Login
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        assert auth_response.status_code == 200
        token = auth_response.json()["access_token"]
        
        # Upload file
        files = {"file": ("test.mp3", VALID_MP3_CONTENT, "audio/mpeg")}
        headers = {"Authorization": f"Bearer {token}"}
        upload_response = client.post("/files/upload", files=files, headers=headers)
        
        assert upload_response.status_code == 200
        file_id = upload_response.json()["file_id"]
        
        # Verify upload
        file_response = client.get(f"/files/{file_id}", headers=headers)
        assert file_response.status_code == 200
        assert file_response.json()["status"] == "ready"

    async def test_security_boundaries(self, client):
        """Test security controls and boundaries."""
        files = {"file": ("test.mp3", VALID_MP3_CONTENT, "audio/mpeg")}
        
        # Test without auth
        response = client.post("/files/upload", files=files)
        assert response.status_code == 401
        
        # Test with invalid token
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 401
        
        # Test file access control
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Try to access another user's file
        response = client.get("/files/other_user_file", headers=headers)
        assert response.status_code == 403

    async def test_invalid_file_handling(self, client):
        """Test handling of various invalid files."""
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test invalid MIME type
        files = {"file": ("test.exe", b"malicious", "application/x-msdownload")}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 415
        
        # Test empty file
        files = {"file": ("empty.mp3", b"", "audio/mpeg")}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 400
        
        # Test malformed file
        files = {"file": ("bad.mp3", b"not_an_mp3", "audio/mpeg")}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 400

    async def test_concurrent_uploads(self, client):
        """Test system behavior with concurrent uploads."""
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Prepare concurrent uploads
        async def upload_file(content):
            files = {"file": ("test.mp3", content, "audio/mpeg")}
            return client.post("/files/upload", files=files, headers=headers)
        
        # Execute concurrent uploads
        start_time = time.time()
        tasks = [
            upload_file(VALID_MP3_CONTENT)
            for _ in range(5)
        ]
        responses = await asyncio.gather(*tasks)
        end_time = time.time()
        
        # Verify results
        assert all(r.status_code == 200 for r in responses)
        assert end_time - start_time < 10  # Should complete within 10 seconds

    async def test_large_file_handling(self, client):
        """Test handling of large file uploads."""
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test large valid file
        files = {"file": ("large.mp3", LARGE_CONTENT, "audio/mpeg")}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 200
        
        # Test file exceeding limit
        huge_content = b"\x00" * (13 * 1024 * 1024 * 1024)  # 13GB
        files = {"file": ("huge.mp3", huge_content, "audio/mpeg")}
        response = client.post("/files/upload", files=files, headers=headers)
        assert response.status_code == 413

    async def test_error_recovery(self, client):
        """Test system recovery from errors."""
        auth_response = client.post("/auth/login", json={
            "username": "test_user",
            "password": "test_pass"
        })
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Upload file
        files = {"file": ("test.mp3", VALID_MP3_CONTENT, "audio/mpeg")}
        response = client.post("/files/upload", files=files, headers=headers)
        file_id = response.json()["file_id"]
        
        # Simulate error during processing
        error_response = client.post(f"/files/{file_id}/process", headers=headers)
        assert error_response.status_code == 500
        
        # Verify system state recovery
        status_response = client.get(f"/files/{file_id}", headers=headers)
        assert status_response.status_code == 200
        assert status_response.json()["status"] != "processing"  # Should not be stuck
