"""Unit tests for ZIP handler service."""

import os
import pytest
import zipfile
import tempfile
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, mock_open
from src.services.zip_handler import ZipHandlerService
from src.services.storage import StorageService
from src.services.encryption import EncryptionService
from src.utils.exceptions import ZipError, StorageError
from src.types import (
    ZipProcessingResult,
    ZipValidationResult,
    ProgressStage
)

@pytest.fixture
def mock_storage_service():
    """Create mock storage service."""
    service = Mock()
    service.store_file = AsyncMock()
    service.store_file.return_value = {
        "path": "/test/path",
        "size": 1000,
        "encrypted": True
    }
    return service

@pytest.fixture
def mock_encryption_service():
    """Create mock encryption service."""
    service = Mock()
    service.encrypt_file = AsyncMock()
    service.decrypt_file = AsyncMock()
    return service

@pytest.fixture
def zip_handler(mock_storage_service, mock_encryption_service):
    """Create ZIP handler service with mocked dependencies."""
    settings = {
        'supported_audio_extensions': ['.mp3', '.wav'],
        'max_zip_size': 1024 * 1024 * 1024,  # 1GB
        'ffmpeg_path': 'ffmpeg'
    }
    service = ZipHandlerService(settings)
    service.storage_service = mock_storage_service
    service.encryption_service = mock_encryption_service
    return service

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

@pytest.mark.asyncio
async def test_process_zip_file_success(zip_handler, test_zip_file):
    """Test successful ZIP file processing."""
    # Mock progress callback
    progress_callback = AsyncMock()
    
    # Process ZIP file
    result = await zip_handler.process_zip_file(
        file_path=test_zip_file,
        job_id="test_job",
        progress_callback=progress_callback,
        encrypt=True
    )
    
    # Verify result
    assert isinstance(result, ZipProcessingResult)
    assert result.is_combined
    assert len(result.original_files) == 2
    assert result.combined_file_id is not None
    
    # Verify storage service calls
    assert zip_handler.storage_service.store_file.call_count == 3  # 2 original + 1 combined
    
    # Verify progress callback calls
    assert progress_callback.call_count > 0
    assert any(call.args[0] == str(ProgressStage.EXTRACTING) for call in progress_callback.mock_calls)
    assert any(call.args[0] == str(ProgressStage.PROCESSING) for call in progress_callback.mock_calls)
    assert any(call.args[0] == str(ProgressStage.COMPLETED) for call in progress_callback.mock_calls)

@pytest.mark.asyncio
async def test_process_zip_file_no_audio(zip_handler):
    """Test ZIP file with no audio files."""
    # Create ZIP with no audio files
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zip_ref:
        zip_ref.writestr("test.txt", b"test content")
    
    try:
        # Process ZIP file
        with pytest.raises(ZipError) as excinfo:
            await zip_handler.process_zip_file(
                file_path=zip_path,
                job_id="test_job"
            )
        
        assert "No audio/video files found in ZIP" in str(excinfo.value)
        
    finally:
        # Clean up
        try:
            os.remove(zip_path)
            os.rmdir(temp_dir)
        except:
            pass

@pytest.mark.asyncio
async def test_process_zip_file_storage_error(zip_handler, test_zip_file):
    """Test storage service error handling."""
    # Mock storage error
    zip_handler.storage_service.store_file.side_effect = StorageError("Storage error")
    
    # Process ZIP file
    with pytest.raises(ZipError) as excinfo:
        await zip_handler.process_zip_file(
            file_path=test_zip_file,
            job_id="test_job"
        )
    
    assert "Failed to store file" in str(excinfo.value)

@pytest.mark.asyncio
async def test_validate_zip_file_success(zip_handler, test_zip_file):
    """Test successful ZIP file validation."""
    # Validate ZIP file
    result = await zip_handler.validate_zip_file(test_zip_file)
    
    # Verify result
    assert isinstance(result, ZipValidationResult)
    assert result.is_valid
    assert result.file_count == 2
    assert len(result.audio_files) == 2
    assert result.total_size > 0
    assert not result.errors

@pytest.mark.asyncio
async def test_validate_zip_file_too_large(zip_handler, test_zip_file):
    """Test ZIP file size validation."""
    # Set small max size
    zip_handler.max_zip_size = 1  # 1 byte
    
    # Validate ZIP file
    result = await zip_handler.validate_zip_file(test_zip_file)
    
    # Verify result
    assert not result.is_valid
    assert "ZIP file too large" in result.errors[0]

@pytest.mark.asyncio
async def test_validate_zip_file_encrypted(zip_handler):
    """Test encrypted ZIP file validation."""
    # Create encrypted ZIP
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "test.zip")
    
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zip_ref:
        zip_ref.setpassword(b"password")
        zip_ref.writestr("test.mp3", b"test content")
    
    try:
        # Validate ZIP file
        result = await zip_handler.validate_zip_file(zip_path)
        
        # Verify result
        assert not result.is_valid
        assert "Encrypted ZIP files are not supported" in result.errors[0]
        
    finally:
        # Clean up
        try:
            os.remove(zip_path)
            os.rmdir(temp_dir)
        except:
            pass

@pytest.mark.asyncio
async def test_validate_audio_file(zip_handler):
    """Test audio file validation."""
    # Mock ffprobe output
    process_mock = AsyncMock()
    process_mock.returncode = 0
    process_mock.communicate.return_value = (b"mp3", b"")
    
    with patch('asyncio.create_subprocess_exec', return_value=process_mock):
        # Validate audio file
        result = await zip_handler.validate_audio_file("test.mp3")
        assert result is True

@pytest.mark.asyncio
async def test_validate_audio_file_invalid(zip_handler):
    """Test invalid audio file validation."""
    # Mock ffprobe error
    process_mock = AsyncMock()
    process_mock.returncode = 1
    process_mock.communicate.return_value = (b"", b"Invalid file")
    
    with patch('asyncio.create_subprocess_exec', return_value=process_mock):
        # Validate audio file
        result = await zip_handler.validate_audio_file("test.mp3")
        assert result is False

@pytest.mark.asyncio
async def test_combine_audio_files(zip_handler):
    """Test audio file combination."""
    # Mock ffmpeg process
    process_mock = AsyncMock()
    process_mock.returncode = 0
    process_mock.communicate.return_value = (b"", b"")
    
    with patch('asyncio.create_subprocess_exec', return_value=process_mock):
        # Combine audio files
        result = await zip_handler.combine_audio_files(
            ["test1.mp3", "test2.mp3"],
            "test_job"
        )
        
        # Verify result
        assert result.endswith("combined_test_job.wav")
        assert os.path.exists(result)
        
        # Clean up
        os.remove(result)

@pytest.mark.asyncio
async def test_combine_audio_files_error(zip_handler):
    """Test audio file combination error."""
    # Mock ffmpeg error
    process_mock = AsyncMock()
    process_mock.returncode = 1
    process_mock.communicate.return_value = (b"", b"Error")
    
    with patch('asyncio.create_subprocess_exec', return_value=process_mock):
        # Combine audio files
        with pytest.raises(ZipError) as excinfo:
            await zip_handler.combine_audio_files(
                ["test1.mp3", "test2.mp3"],
                "test_job"
            )
        
        assert "Failed to combine audio files" in str(excinfo.value)

def test_is_supported_audio_file(zip_handler):
    """Test audio file extension checking."""
    assert zip_handler.is_supported_audio_file("test.mp3") is True
    assert zip_handler.is_supported_audio_file("test.wav") is True
    assert zip_handler.is_supported_audio_file("test.txt") is False
    assert zip_handler.is_supported_audio_file("test") is False

def test_is_zip_file(zip_handler):
    """Test ZIP file checking."""
    assert zip_handler.is_zip_file("test.zip") is True
    assert zip_handler.is_zip_file("test.ZIP") is True
    assert zip_handler.is_zip_file("test.txt") is False
    assert zip_handler.is_zip_file("test") is False
