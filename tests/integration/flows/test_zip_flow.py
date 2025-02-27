"""Integration tests for ZIP handling flow."""

import os
import pytest
import zipfile
import tempfile
from typing import Dict, Any
from fastapi.testclient import TestClient
from src.main import app
from src.types import (
    JobType,
    JobPriority,
    ProgressStage,
    ZipValidationResult,
    ZipFileInfo
)

@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def test_zip_file():
    """Create test ZIP file with audio files."""
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    # Create test audio files
    audio_files = [
        ("test1.mp3", b"test audio content 1"),
        ("test2.wav", b"test audio content 2")
    ]
    
    with zipfile.ZipFile(zip_path, 'w') as zip_ref:
        for filename, content in audio_files:
            zip_ref.writestr(filename, content)
    
    yield zip_path
    
    # Clean up
    try:
        os.remove(zip_path)
        os.rmdir(temp_dir)
    except:
        pass

@pytest.fixture
def test_metadata():
    """Create test metadata."""
    return {
        "language": "en",
        "options": {
            "diarization": True,
            "timestamps": True
        }
    }

def test_zip_upload_flow(test_client, test_zip_file, test_metadata):
    """Test complete ZIP upload and processing flow."""
    # Upload ZIP file
    with open(test_zip_file, "rb") as f:
        response = test_client.post(
            "/zip/process",
            files={"file": ("test.zip", f, "application/zip")},
            data={
                "metadata": test_metadata,
                "encrypt": True
            }
        )
    
    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "processing"
    
    job_id = data["job_id"]
    
    # Monitor job progress
    max_attempts = 10
    for _ in range(max_attempts):
        response = test_client.get(f"/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        
        if job["metadata"]["stage"] == str(ProgressStage.COMPLETED):
            break
        elif job["metadata"]["stage"] == str(ProgressStage.FAILED):
            pytest.fail(f"Job failed: {job['metadata'].get('error')}")
            
        # Wait before next check
        import time
        time.sleep(1)
    else:
        pytest.fail("Job did not complete in time")
    
    # Verify job completion
    assert job["metadata"]["stage"] == str(ProgressStage.COMPLETED)
    assert job["metadata"]["progress"] == 100
    assert "child_jobs" in job["metadata"]
    assert len(job["metadata"]["child_jobs"]) > 0
    
    # Check transcription job
    transcription_job_id = job["metadata"]["child_jobs"][0]
    response = test_client.get(f"/jobs/{transcription_job_id}")
    assert response.status_code == 200
    transcription_job = response.json()
    
    # Verify transcription job
    assert transcription_job["type"] == JobType.TRANSCRIPTION
    assert transcription_job["metadata"]["parent_job_id"] == job_id
    assert "file_id" in transcription_job["metadata"]

def test_zip_validation_flow(test_client, test_zip_file):
    """Test ZIP file validation flow."""
    # Validate ZIP file
    with open(test_zip_file, "rb") as f:
        response = test_client.post(
            "/zip/validate",
            files={"file": ("test.zip", f, "application/zip")}
        )
    
    # Verify response
    assert response.status_code == 200
    result = ZipValidationResult(**response.json())
    assert result.is_valid
    assert result.file_count == 2
    assert len(result.audio_files) == 2
    assert result.total_size > 0
    assert not result.errors

def test_zip_info_flow(test_client, test_zip_file):
    """Test ZIP file info flow."""
    # Get ZIP info
    with open(test_zip_file, "rb") as f:
        response = test_client.post(
            "/zip/info",
            files={"file": ("test.zip", f, "application/zip")}
        )
    
    # Verify response
    assert response.status_code == 200
    info = ZipFileInfo(**response.json())
    assert info.filename == "test.zip"
    assert info.size > 0
    assert len(info.files) == 2
    assert not info.is_encrypted
    assert info.comment is None

def test_invalid_zip_file(test_client):
    """Test invalid ZIP file handling."""
    # Create invalid file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(b"not a zip file")
    temp_file.close()
    
    try:
        # Try to process invalid file
        with open(temp_file.name, "rb") as f:
            response = test_client.post(
                "/zip/process",
                files={"file": ("test.zip", f, "application/zip")}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "Invalid ZIP file" in response.json()["detail"]
        
    finally:
        # Clean up
        os.unlink(temp_file.name)

def test_encrypted_zip_file(test_client):
    """Test encrypted ZIP file handling."""
    # Create encrypted ZIP
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_ref:
        zip_ref.setpassword(b"password")
        zip_ref.writestr("test.mp3", b"test content")
    
    try:
        # Try to process encrypted file
        with open(zip_path, "rb") as f:
            response = test_client.post(
                "/zip/process",
                files={"file": ("test.zip", f, "application/zip")}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "Encrypted ZIP files are not supported" in response.json()["detail"]
        
    finally:
        # Clean up
        try:
            os.remove(zip_path)
            os.rmdir(temp_dir)
        except:
            pass

def test_no_audio_files(test_client):
    """Test ZIP file with no audio files."""
    # Create ZIP with no audio files
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zip_ref:
        zip_ref.writestr("test.txt", b"test content")
    
    try:
        # Try to process file
        with open(zip_path, "rb") as f:
            response = test_client.post(
                "/zip/process",
                files={"file": ("test.zip", f, "application/zip")}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "No audio/video files found in ZIP" in response.json()["detail"]
        
    finally:
        # Clean up
        try:
            os.remove(zip_path)
            os.rmdir(temp_dir)
        except:
            pass

def test_large_zip_file(test_client):
    """Test large ZIP file handling."""
    # Create large ZIP file
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zip_ref:
        # Create large file (1GB)
        large_file = os.path.join(temp_dir, "large.mp3")
        with open(large_file, "wb") as f:
            f.seek(1024 * 1024 * 1024 - 1)  # 1GB - 1 byte
            f.write(b"\0")
        
        zip_ref.write(large_file, "large.mp3")
        os.remove(large_file)
    
    try:
        # Try to process large file
        with open(zip_path, "rb") as f:
            response = test_client.post(
                "/zip/process",
                files={"file": ("test.zip", f, "application/zip")}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "ZIP file too large" in response.json()["detail"]
        
    finally:
        # Clean up
        try:
            os.remove(zip_path)
            os.rmdir(temp_dir)
        except:
            pass

def test_concurrent_uploads(test_client, test_zip_file):
    """Test concurrent ZIP file uploads."""
    import asyncio
    import aiohttp
    
    async def upload_file():
        async with aiohttp.ClientSession() as session:
            with open(test_zip_file, "rb") as f:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    f,
                    filename="test.zip",
                    content_type="application/zip"
                )
                async with session.post(
                    "http://testserver/zip/process",
                    data=data
                ) as response:
                    return await response.json()
    
    # Upload multiple files concurrently
    async def run_uploads():
        tasks = [upload_file() for _ in range(3)]
        return await asyncio.gather(*tasks)
    
    # Run uploads
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(run_uploads())
    
    # Verify results
    assert len(results) == 3
    for result in results:
        assert "job_id" in result
        assert result["status"] == "processing"
