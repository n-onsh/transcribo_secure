"""Integration tests for upload flow."""

import os
import asyncio
import zipfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import patch

from frontend.src.main import app
from frontend.src.components.upload import UploadComponent

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def test_files(tmp_path):
    """Create test audio files."""
    files = []
    
    # Create MP3 file
    mp3_path = tmp_path / "test.mp3"
    mp3_path.write_bytes(b"test mp3 data" * 1000)  # ~12KB
    files.append(mp3_path)
    
    # Create WAV file
    wav_path = tmp_path / "test.wav"
    wav_path.write_bytes(b"test wav data" * 1000)  # ~12KB
    files.append(wav_path)
    
    # Create ZIP file
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for file in files:
            zip_file.write(file, file.name)
    files.append(zip_path)
    
    return files

@pytest.mark.asyncio
async def test_render_upload_page(client):
    """Test rendering upload page."""
    response = client.get("/upload")
    assert response.status_code == 200
    assert "Upload Audio Files" in response.text
    assert "Language" in response.text
    assert "Supported file types" in response.text

@pytest.mark.asyncio
async def test_upload_single_file(client, test_files):
    """Test uploading single audio file."""
    mp3_file = test_files[0]
    
    with open(mp3_file, 'rb') as f:
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.mp3", f, "audio/mpeg")},
            data={"language": "en"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["file_name"] == "test.mp3"
    assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_upload_zip_file(client, test_files):
    """Test uploading ZIP file."""
    zip_file = test_files[2]
    
    with open(zip_file, 'rb') as f:
        response = client.post(
            "/api/zip/upload",
            files={"file": ("test.zip", f, "application/zip")},
            data={"language": "en"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # Two files in ZIP
    for job in data:
        assert "id" in job
        assert job["status"] == "pending"
        assert job["file_name"] in ["test.mp3", "test.wav"]

@pytest.mark.asyncio
async def test_file_validation(client, test_files):
    """Test file validation."""
    # Test invalid file type
    with open(__file__, 'rb') as f:
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.py", f, "text/plain")},
            data={"language": "en"}
        )
    
    assert response.status_code == 400
    assert "invalid file type" in response.json()["detail"].lower()
    
    # Test file too large
    large_file = test_files[0].parent / "large.mp3"
    large_file.write_bytes(b"0" * (2 * 1024 * 1024 * 1024))  # 2GB
    
    with open(large_file, 'rb') as f:
        response = client.post(
            "/api/files/upload",
            files={"file": ("large.mp3", f, "audio/mpeg")},
            data={"language": "en"}
        )
    
    assert response.status_code == 400
    assert "too large" in response.json()["detail"].lower()
    
    # Cleanup
    os.remove(large_file)

@pytest.mark.asyncio
async def test_language_validation(client, test_files):
    """Test language validation."""
    mp3_file = test_files[0]
    
    # Test invalid language
    with open(mp3_file, 'rb') as f:
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.mp3", f, "audio/mpeg")},
            data={"language": "invalid"}
        )
    
    assert response.status_code == 400
    assert "invalid language" in response.json()["detail"].lower()
    
    # Test missing language
    with open(mp3_file, 'rb') as f:
        response = client.post(
            "/api/files/upload",
            files={"file": ("test.mp3", f, "audio/mpeg")}
        )
    
    assert response.status_code == 400
    assert "language required" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_zip_extraction_progress(client, test_files):
    """Test ZIP extraction progress tracking."""
    zip_file = test_files[2]
    
    with open(zip_file, 'rb') as f:
        # Start upload
        response = client.post(
            "/api/zip/upload",
            files={"file": ("test.zip", f, "application/zip")},
            data={"language": "en"}
        )
        
        assert response.status_code == 200
        file_id = response.json()[0]["id"]
        
        # Check progress
        response = client.get(f"/api/zip/progress/{file_id}")
        assert response.status_code == 200
        data = response.json()
        assert "progress" in data
        assert isinstance(data["progress"], float)
        assert 0 <= data["progress"] <= 100

@pytest.mark.asyncio
async def test_zip_extraction_cancellation(client, test_files):
    """Test cancelling ZIP extraction."""
    zip_file = test_files[2]
    
    with open(zip_file, 'rb') as f:
        # Start upload
        response = client.post(
            "/api/zip/upload",
            files={"file": ("test.zip", f, "application/zip")},
            data={"language": "en"}
        )
        
        assert response.status_code == 200
        file_id = response.json()[0]["id"]
        
        # Cancel extraction
        response = client.delete(f"/api/zip/{file_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"
        
        # Verify cancelled
        response = client.get(f"/api/zip/progress/{file_id}")
        assert response.status_code == 404

@pytest.mark.asyncio
async def test_concurrent_uploads(client, test_files):
    """Test handling concurrent uploads."""
    mp3_file = test_files[0]
    wav_file = test_files[1]
    
    async def upload_file(file_path):
        with open(file_path, 'rb') as f:
            response = await client.post(
                "/api/files/upload",
                files={"file": (file_path.name, f, "audio/mpeg")},
                data={"language": "en"}
            )
            return response
    
    # Upload files concurrently
    responses = await asyncio.gather(
        upload_file(mp3_file),
        upload_file(wav_file)
    )
    
    # Verify both uploads succeeded
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"

@pytest.mark.asyncio
async def test_upload_component_integration(client):
    """Test upload component integration."""
    # Get upload page
    response = client.get("/upload")
    assert response.status_code == 200
    
    # Check language selector
    assert 'id="language-select"' in response.text
    assert "German" in response.text
    assert "English" in response.text
    
    # Check file type info
    assert ".mp3" in response.text
    assert ".wav" in response.text
    assert ".m4a" in response.text
    assert ".zip" in response.text
    
    # Check tooltips
    assert 'data-bs-toggle="tooltip"' in response.text
    assert "language" in response.text
    assert "file types" in response.text
    
    # Check drag & drop
    assert 'id="drop-zone"' in response.text
    assert "Drag and drop" in response.text
    
    # Check validation display
    assert 'id="validation-errors"' in response.text
    
    # Check progress display
    assert 'id="progress-bar"' in response.text
