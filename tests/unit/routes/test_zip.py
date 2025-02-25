"""Tests for ZIP file upload routes."""

import os
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from fastapi import UploadFile
from fastapi.testclient import TestClient

from backend.src.main import app
from backend.src.models.job import Job, JobStatus

@pytest.fixture
def mock_job_manager():
    """Create mock job manager"""
    manager = Mock()
    manager.db = Mock()
    manager.db.pool = Mock()
    manager.db.pool.acquire = AsyncMock()
    return manager

@pytest.fixture
def mock_storage():
    """Create mock storage service"""
    storage = Mock()
    storage.upload_file = AsyncMock()
    return storage

@pytest.fixture
def mock_zip_handler():
    """Create mock ZIP handler"""
    handler = Mock()
    handler.validate_zip = AsyncMock()
    handler.extract_zip = AsyncMock()
    handler.get_extraction_progress = AsyncMock()
    handler.cancel_extraction = AsyncMock()
    return handler

@pytest.fixture
def client(mock_job_manager, mock_storage, mock_zip_handler):
    """Create test client with mocked dependencies"""
    app.dependency_overrides[JobManager] = lambda: mock_job_manager
    app.dependency_overrides[StorageService] = lambda: mock_storage
    app.dependency_overrides[ZipHandler] = lambda: mock_zip_handler
    return TestClient(app)

@pytest.fixture
def test_file():
    """Create test ZIP file"""
    content = b"test zip content"
    return {
        "file": ("test.zip", content, "application/zip")
    }

@pytest.mark.asyncio
async def test_upload_zip_success(client, test_file, mock_zip_handler, mock_job_manager):
    """Test successful ZIP upload"""
    # Setup mocks
    mock_zip_handler.validate_zip.return_value = (True, None)
    mock_zip_handler.extract_zip.return_value = [
        ("test1.mp3", 33.33),
        ("test2.mp3", 66.66),
        ("test3.mp3", 100.0)
    ]
    
    # Setup database mock
    conn = AsyncMock()
    mock_job_manager.db.pool.acquire.return_value.__aenter__.return_value = conn
    conn.fetch.return_value = [
        {
            "id": str(uuid4()),
            "owner_id": str(uuid4()),
            "file_name": "test1.mp3",
            "status": JobStatus.PENDING.value,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    # Upload file
    response = client.post(
        "/zip/upload",
        files=test_file,
        data={"language": "en"}
    )
    
    # Verify response
    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == JobStatus.PENDING.value
    
    # Verify calls
    mock_zip_handler.validate_zip.assert_called_once()
    mock_zip_handler.extract_zip.assert_called_once()
    conn.fetch.assert_called_once()

@pytest.mark.asyncio
async def test_upload_zip_validation_error(client, test_file, mock_zip_handler):
    """Test ZIP upload with validation error"""
    # Setup mock to return validation error
    mock_zip_handler.validate_zip.return_value = (False, "Invalid ZIP file")
    
    # Upload file
    response = client.post(
        "/zip/upload",
        files=test_file
    )
    
    # Verify error response
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid ZIP file"
    
    # Verify no extraction attempted
    mock_zip_handler.extract_zip.assert_not_called()

@pytest.mark.asyncio
async def test_upload_zip_extraction_error(client, test_file, mock_zip_handler):
    """Test ZIP upload with extraction error"""
    # Setup mocks
    mock_zip_handler.validate_zip.return_value = (True, None)
    mock_zip_handler.extract_zip.side_effect = Exception("Extraction failed")
    
    # Upload file
    response = client.post(
        "/zip/upload",
        files=test_file
    )
    
    # Verify error response
    assert response.status_code == 500
    assert "Failed to process ZIP file" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_progress(client, mock_zip_handler):
    """Test getting ZIP extraction progress"""
    file_id = uuid4()
    mock_zip_handler.get_extraction_progress.return_value = 50.0
    
    # Get progress
    response = client.get(f"/zip/progress/{file_id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == str(file_id)
    assert data["progress"] == 50.0

@pytest.mark.asyncio
async def test_get_progress_error(client, mock_zip_handler):
    """Test getting progress with error"""
    file_id = uuid4()
    mock_zip_handler.get_extraction_progress.side_effect = Exception("Failed")
    
    # Get progress
    response = client.get(f"/zip/progress/{file_id}")
    
    # Verify error response
    assert response.status_code == 500
    assert "Failed to get progress" in response.json()["detail"]

@pytest.mark.asyncio
async def test_cancel_extraction(client, mock_zip_handler):
    """Test cancelling ZIP extraction"""
    file_id = uuid4()
    
    # Cancel extraction
    response = client.delete(f"/zip/{file_id}")
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["file_id"] == str(file_id)
    assert data["status"] == "cancelled"
    
    # Verify handler called
    mock_zip_handler.cancel_extraction.assert_called_once_with(file_id)

@pytest.mark.asyncio
async def test_cancel_extraction_error(client, mock_zip_handler):
    """Test cancelling extraction with error"""
    file_id = uuid4()
    mock_zip_handler.cancel_extraction.side_effect = Exception("Failed")
    
    # Cancel extraction
    response = client.delete(f"/zip/{file_id}")
    
    # Verify error response
    assert response.status_code == 500
    assert "Failed to cancel extraction" in response.json()["detail"]

@pytest.mark.asyncio
async def test_cleanup_after_upload(client, test_file, mock_zip_handler):
    """Test temp file cleanup after upload"""
    # Setup mocks
    mock_zip_handler.validate_zip.return_value = (True, None)
    mock_zip_handler.extract_zip.return_value = []
    
    with patch('tempfile.NamedTemporaryFile') as mock_temp:
        # Setup temp file mock
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.zip"
        mock_temp.return_value.__enter__.return_value = mock_temp_file
        
        # Upload file
        response = client.post(
            "/zip/upload",
            files=test_file
        )
        
        # Verify temp file removed
        assert not os.path.exists("/tmp/test.zip")

@pytest.mark.asyncio
async def test_upload_with_language(client, test_file, mock_zip_handler):
    """Test ZIP upload with language specified"""
    # Setup mocks
    mock_zip_handler.validate_zip.return_value = (True, None)
    mock_zip_handler.extract_zip.return_value = []
    
    # Upload file with language
    response = client.post(
        "/zip/upload",
        files=test_file,
        data={"language": "de"}
    )
    
    # Verify language passed to handler
    mock_zip_handler.extract_zip.assert_called_once()
    assert mock_zip_handler.extract_zip.call_args[1]["language"] == "de"

@pytest.mark.asyncio
async def test_metrics_tracking(client, test_file, mock_zip_handler):
    """Test metrics are tracked during upload"""
    # Setup mocks
    mock_zip_handler.validate_zip.return_value = (True, None)
    mock_zip_handler.extract_zip.return_value = []
    
    with patch('backend.src.routes.zip.API_REQUEST_SIZE') as mock_size_metric, \
         patch('backend.src.routes.zip.API_ERROR_COUNT') as mock_error_metric:
        
        # Upload file
        response = client.post(
            "/zip/upload",
            files=test_file
        )
        
        # Verify metrics recorded
        mock_size_metric.record.assert_called_once()
        mock_error_metric.inc.assert_not_called()
