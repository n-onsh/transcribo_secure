"""
Integration Test Suite for Streaming File Uploads

This test suite verifies the streaming upload functionality including:
1. Chunk-by-chunk processing
2. Progress tracking
3. Memory efficiency
4. Error handling
"""
import pytest
import io
import asyncio
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock, call
from backend.src.services.storage import StorageService
from backend.src.services.job_manager import JobManager
from backend.src.models.job import Job, JobStatus
from backend.src.routes.files import router

# Test data
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB chunks
LARGE_FILE_SIZE = 100 * 1024 * 1024  # 100MB for testing
TEST_USER_ID = "test_user"

@pytest.fixture
def mock_storage():
    """Mock storage service with streaming support."""
    mock = AsyncMock()
    with patch("backend.src.services.provider.service_provider.get", return_value=mock) as _:
        yield mock

@pytest.fixture
def mock_job_manager():
    """Mock job manager with progress tracking."""
    mock = AsyncMock()
    with patch("backend.src.services.provider.service_provider.get", return_value=mock) as _:
        yield mock

@pytest.fixture
def app(mock_storage, mock_job_manager):
    """Create test FastAPI application."""
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def large_file():
    """Create a large test file."""
    return io.BytesIO(b"x" * LARGE_FILE_SIZE)

class TestStreamingUploads:
    """Test suite for streaming file uploads."""

    async def test_streaming_upload_success(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test successful streaming upload with progress tracking."""
        # Setup mocks
        job = Job(
            id="test_job",
            user_id=TEST_USER_ID,
            file_name="test.mp3",
            file_size=LARGE_FILE_SIZE,
            status=JobStatus.PENDING
        )
        mock_job_manager.create_job.return_value = job
        
        # Track progress updates
        progress_updates = []
        async def mock_store_file(*args, **kwargs):
            if 'progress_callback' in kwargs:
                # Simulate progress updates
                for progress in [25.0, 50.0, 75.0, 100.0]:
                    await kwargs['progress_callback'](progress)
                    progress_updates.append(progress)
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["id"] == "test_job"
        assert response.json()["progress"] == 100.0
        
        # Verify streaming
        mock_storage.store_file.assert_called_once()
        assert len(progress_updates) == 4
        assert progress_updates == [25.0, 50.0, 75.0, 100.0]

    async def test_streaming_upload_memory_usage(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test that streaming upload maintains efficient memory usage."""
        # Setup mocks
        job = Job(
            id="test_job",
            user_id=TEST_USER_ID,
            file_name="test.mp3",
            file_size=LARGE_FILE_SIZE,
            status=JobStatus.PENDING
        )
        mock_job_manager.create_job.return_value = job
        
        # Track chunk sizes
        chunk_sizes = []
        async def mock_store_file(*args, **kwargs):
            data = args[1]  # data is the second argument
            # Read chunks to verify size
            while True:
                chunk = data.read(CHUNK_SIZE)
                if not chunk:
                    break
                chunk_sizes.append(len(chunk))
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify response
        assert response.status_code == 201
        
        # Verify chunk sizes
        assert all(size <= CHUNK_SIZE for size in chunk_sizes)
        assert sum(chunk_sizes) == LARGE_FILE_SIZE

    async def test_streaming_upload_error_handling(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test error handling during streaming upload."""
        # Setup mocks to fail partway through
        async def mock_store_file(*args, **kwargs):
            if 'progress_callback' in kwargs:
                # Simulate progress before error
                await kwargs['progress_callback'](50.0)
                raise IOError("Storage error during upload")
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify error response
        assert response.status_code == 500
        assert "File upload failed" in response.json()["detail"]

    async def test_streaming_upload_progress_tracking(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test detailed progress tracking during upload."""
        # Setup mocks
        job = Job(
            id="test_job",
            user_id=TEST_USER_ID,
            file_name="test.mp3",
            file_size=LARGE_FILE_SIZE,
            status=JobStatus.PENDING
        )
        mock_job_manager.create_job.return_value = job
        
        # Track progress updates with timestamps
        progress_updates = []
        async def mock_store_file(*args, **kwargs):
            if 'progress_callback' in kwargs:
                # Simulate gradual progress
                for i in range(0, 101, 10):
                    progress = float(i)
                    await kwargs['progress_callback'](progress)
                    progress_updates.append(progress)
                    await asyncio.sleep(0.1)  # Simulate processing time
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify response
        assert response.status_code == 201
        assert response.json()["progress"] == 100.0
        
        # Verify progress tracking
        assert len(progress_updates) == 11  # 0 to 100 by 10
        assert progress_updates == [float(i) for i in range(0, 101, 10)]

    async def test_streaming_upload_cancellation(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test handling of upload cancellation."""
        # Setup mocks to simulate cancellation
        async def mock_store_file(*args, **kwargs):
            if 'progress_callback' in kwargs:
                # Simulate progress before cancellation
                await kwargs['progress_callback'](30.0)
                raise asyncio.CancelledError()
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify error response
        assert response.status_code == 500
        assert "Upload cancelled" in response.json()["detail"]

    async def test_streaming_upload_validation(self, app, client, mock_storage, mock_job_manager):
        """Test validation during streaming upload."""
        # Test various invalid scenarios
        test_cases = [
            (
                io.BytesIO(b""),  # Empty file
                "empty.mp3",
                400,
                "The file appears to be empty"
            ),
            (
                io.BytesIO(b"x" * (12 * 1024 * 1024 * 1024 + 1)),  # Too large
                "large.mp3",
                413,
                "This file is too large"
            ),
            (
                io.BytesIO(b"invalid"),  # Invalid content
                "test.exe",
                400,
                "This file type is not allowed"
            )
        ]
        
        for content, filename, expected_status, expected_error in test_cases:
            files = {"file": (filename, content, "audio/mpeg")}
            response = client.post("/files/", files=files)
            
            assert response.status_code == expected_status
            assert expected_error in response.json()["detail"]

    async def test_streaming_upload_retry(self, app, client, mock_storage, mock_job_manager, large_file):
        """Test upload retry after temporary failure."""
        # Setup mocks to fail once then succeed
        attempt = 0
        async def mock_store_file(*args, **kwargs):
            nonlocal attempt
            if attempt == 0:
                attempt += 1
                raise IOError("Temporary storage error")
            if 'progress_callback' in kwargs:
                await kwargs['progress_callback'](100.0)
        mock_storage.store_file.side_effect = mock_store_file
        
        # Test file upload
        files = {"file": ("test.mp3", large_file, "audio/mpeg")}
        
        # First attempt should fail
        response = client.post("/files/", files=files)
        assert response.status_code == 500
        
        # Reset file position
        large_file.seek(0)
        
        # Second attempt should succeed
        response = client.post("/files/", files=files)
        assert response.status_code == 201
        assert response.json()["progress"] == 100.0
