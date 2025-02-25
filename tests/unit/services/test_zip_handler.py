"""Tests for ZIP file handling service."""

import asyncio
import os
import pytest
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from backend.src.models.file import File
from backend.src.models.job import Job, JobStatus
from backend.src.services.zip_handler import ZipHandler

@pytest.fixture
def mock_storage():
    """Create mock storage service"""
    storage = Mock()
    storage.upload_file = AsyncMock()
    return storage

@pytest.fixture
def mock_job_manager():
    """Create mock job manager"""
    manager = Mock()
    manager.create_job = AsyncMock()
    return manager

@pytest.fixture
def zip_handler(mock_storage, mock_job_manager):
    """Create ZIP handler with mocked dependencies"""
    return ZipHandler(
        storage=mock_storage,
        job_manager=mock_job_manager,
        max_file_size=1024 * 1024,  # 1MB for tests
        max_files=5,
        allowed_extensions={'mp3', 'wav'},
        chunk_size=1024,  # 1KB for tests
        extraction_timeout=5  # 5 seconds for tests
    )

@pytest.fixture
def test_files(tmp_path):
    """Create test audio files"""
    files = []
    for i in range(3):
        file_path = tmp_path / f"test_{i}.mp3"
        file_path.write_bytes(b"test audio data")
        files.append(file_path)
    return files

@pytest.fixture
def test_zip(tmp_path, test_files):
    """Create test ZIP file"""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for file_path in test_files:
            zip_file.write(file_path, file_path.name)
    return zip_path

@pytest.mark.asyncio
async def test_validate_zip_success(zip_handler, test_zip):
    """Test successful ZIP validation"""
    valid, error = await zip_handler.validate_zip(test_zip)
    assert valid
    assert error is None

@pytest.mark.asyncio
async def test_validate_zip_too_many_files(zip_handler, tmp_path):
    """Test ZIP with too many files"""
    # Create ZIP with too many files
    zip_path = tmp_path / "too_many.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for i in range(10):  # More than max_files
            zip_file.writestr(f"test_{i}.mp3", b"test data")
    
    valid, error = await zip_handler.validate_zip(zip_path)
    assert not valid
    assert "too many files" in error.lower()

@pytest.mark.asyncio
async def test_validate_zip_invalid_extension(zip_handler, tmp_path):
    """Test ZIP with invalid file types"""
    zip_path = tmp_path / "invalid_types.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        zip_file.writestr("test.txt", b"test data")
    
    valid, error = await zip_handler.validate_zip(zip_path)
    assert not valid
    assert "invalid file types" in error.lower()

@pytest.mark.asyncio
async def test_validate_zip_too_large(zip_handler, tmp_path):
    """Test ZIP with content too large"""
    zip_path = tmp_path / "too_large.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        # Create file larger than max_file_size
        zip_file.writestr("large.mp3", b"0" * (2 * 1024 * 1024))
    
    valid, error = await zip_handler.validate_zip(zip_path)
    assert not valid
    assert "too large" in error.lower()

@pytest.mark.asyncio
async def test_validate_zip_corrupted(zip_handler, tmp_path):
    """Test corrupted ZIP file"""
    zip_path = tmp_path / "corrupted.zip"
    zip_path.write_bytes(b"not a zip file")
    
    valid, error = await zip_handler.validate_zip(zip_path)
    assert not valid
    assert "invalid zip file format" in error.lower()

@pytest.mark.asyncio
async def test_extract_zip_success(zip_handler, test_zip):
    """Test successful ZIP extraction"""
    file_id = uuid4()
    owner_id = uuid4()
    
    filenames = []
    progress_values = []
    
    async for filename, progress in zip_handler.extract_zip(
        file_id=file_id,
        owner_id=owner_id,
        file_path=str(test_zip),
        language="en"
    ):
        filenames.append(filename)
        progress_values.append(progress)
    
    # Verify files processed
    assert len(filenames) == 3
    assert all(f.endswith('.mp3') for f in filenames)
    
    # Verify progress reported
    assert len(progress_values) == 3
    assert progress_values[-1] == 100.0
    
    # Verify storage calls
    assert zip_handler.storage.upload_file.call_count == 3
    
    # Verify job creation
    assert zip_handler.job_manager.create_job.call_count == 3
    for call_args in zip_handler.job_manager.create_job.call_args_list:
        job = call_args[1]['job']
        assert isinstance(job, Job)
        assert job.owner_id == owner_id
        assert job.status == JobStatus.PENDING

@pytest.mark.asyncio
async def test_extract_zip_timeout(zip_handler, test_zip):
    """Test ZIP extraction timeout"""
    # Patch storage to simulate slow upload
    async def slow_upload(*args, **kwargs):
        await asyncio.sleep(10)  # Longer than timeout
    zip_handler.storage.upload_file.side_effect = slow_upload
    
    with pytest.raises(asyncio.TimeoutError):
        async for _ in zip_handler.extract_zip(
            file_id=uuid4(),
            owner_id=uuid4(),
            file_path=str(test_zip)
        ):
            pass

@pytest.mark.asyncio
async def test_extract_zip_error_handling(zip_handler, test_zip):
    """Test error handling during extraction"""
    # Patch storage to raise error
    zip_handler.storage.upload_file.side_effect = Exception("Upload failed")
    
    with pytest.raises(Exception) as exc:
        async for _ in zip_handler.extract_zip(
            file_id=uuid4(),
            owner_id=uuid4(),
            file_path=str(test_zip)
        ):
            pass
    
    assert "Upload failed" in str(exc.value)

@pytest.mark.asyncio
async def test_cancel_extraction(zip_handler, test_zip):
    """Test extraction cancellation"""
    file_id = uuid4()
    
    # Start extraction in background
    extraction_task = asyncio.create_task(
        zip_handler.extract_zip(
            file_id=file_id,
            owner_id=uuid4(),
            file_path=str(test_zip)
        ).__aiter__()
    )
    
    # Wait for task to start
    await asyncio.sleep(0.1)
    
    # Cancel extraction
    await zip_handler.cancel_extraction(file_id)
    
    # Verify task cancelled
    with pytest.raises(asyncio.CancelledError):
        await extraction_task

@pytest.mark.asyncio
async def test_get_extraction_progress(zip_handler, test_zip):
    """Test extraction progress tracking"""
    file_id = uuid4()
    
    # Start extraction
    extraction = zip_handler.extract_zip(
        file_id=file_id,
        owner_id=uuid4(),
        file_path=str(test_zip)
    )
    
    # Get progress before completion
    progress = await zip_handler.get_extraction_progress(file_id)
    assert progress is None  # No progress yet
    
    # Complete extraction
    async for _ in extraction:
        pass
    
    # Get progress after completion
    progress = await zip_handler.get_extraction_progress(file_id)
    assert progress is None  # Extraction complete

@pytest.mark.asyncio
async def test_cleanup_after_extraction(zip_handler, test_zip, tmp_path):
    """Test cleanup after extraction"""
    file_id = uuid4()
    
    # Create temp file to verify cleanup
    test_file = tmp_path / "test.mp3"
    test_file.write_bytes(b"test data")
    
    with patch('backend.src.services.zip_handler.open'):
        async for _ in zip_handler.extract_zip(
            file_id=file_id,
            owner_id=uuid4(),
            file_path=str(test_zip)
        ):
            pass
    
    # Verify ZIP file removed
    assert not os.path.exists(test_zip)
    
    # Verify temp files removed
    assert not os.path.exists(test_file)

@pytest.mark.asyncio
async def test_concurrent_extractions(zip_handler, test_zip):
    """Test handling multiple concurrent extractions"""
    file_ids = [uuid4() for _ in range(3)]
    owner_id = uuid4()
    
    # Start multiple extractions
    tasks = [
        asyncio.create_task(
            zip_handler.extract_zip(
                file_id=file_id,
                owner_id=owner_id,
                file_path=str(test_zip)
            ).__aiter__()
        )
        for file_id in file_ids
    ]
    
    # Wait for all to complete
    await asyncio.gather(*tasks)
    
    # Verify all processed
    assert zip_handler.storage.upload_file.call_count == 9  # 3 files * 3 extractions
    assert zip_handler.job_manager.create_job.call_count == 9
