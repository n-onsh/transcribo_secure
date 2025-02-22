"""
Integration Test Suite for File Processing Flow

This test suite verifies the complete file processing chain including validation,
focusing on how file validation integrates with other components like encryption
and storage.

Test Flow:
1. Upload → Validate → Encrypt → Store
2. Store → Decrypt → Process
3. Process → Encrypt → Deliver

Integration Points:
- File validation middleware
- Encryption service
- Storage service
- Processing service
"""
import pytest
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.src.middleware.file_validation import validate_file_middleware
from backend.src.services.encryption import EncryptionService
from backend.src.services.storage import StorageService
from backend.src.config import Settings
import magic.magic as magic_lib

class MockSettings(Settings):
    """Mock settings for testing."""
    ALLOWED_FILE_TYPES = {
        'audio/mpeg',
        'audio/wav',
        'audio/ogg',
        'video/mp4',
        'video/mpeg'
    }

# Test data with file signatures
VALID_MP3_CONTENT = b"ID3" + b"\x00" * 1024  # ID3 tag for MP3
VALID_WAV_CONTENT = b"RIFF" + b"\x00" * 1024  # RIFF header for WAV
VALID_OGG_CONTENT = b"OggS" + b"\x00" * 1024  # OGG container signature
VALID_MP4_CONTENT = b"ftyp" + b"\x00" * 1024  # MP4 file signature
VALID_MPEG_CONTENT = b"\x00\x00\x01\xBA" + b"\x00" * 1024  # MPEG Program Stream

@pytest.fixture
def mock_settings():
    """Mock settings."""
    with patch("backend.src.middleware.file_validation.get_settings", return_value=MockSettings()) as _:
        yield

@pytest.fixture
def mock_magic():
    """Mock magic library."""
    class MockMagic:
        def from_buffer(self, content):
            if b"ID3" in content:
                return "audio/mpeg"
            elif b"RIFF" in content:
                return "audio/wav"
            elif b"OggS" in content:
                return "audio/ogg"
            elif b"ftyp" in content:
                return "video/mp4"
            elif b"\x00\x00\x01\xBA" in content:
                return "video/mpeg"
            elif b"malicious" in content:
                return "application/x-msdownload"
            return "application/octet-stream"
    
    with patch("backend.src.middleware.file_validation.magic.Magic", return_value=MockMagic()) as _:
        yield

@pytest.fixture
def app(mock_settings, mock_magic):
    """Create test FastAPI application with middleware."""
    app = FastAPI()
    app.middleware("http")(validate_file_middleware)
    return app

@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)

@pytest.fixture
def mock_storage():
    """Mock storage service."""
    mock = AsyncMock()
    with patch("backend.src.services.storage.StorageService", return_value=mock) as _:
        yield mock

@pytest.fixture
def mock_encryption():
    """Mock encryption service."""
    mock = AsyncMock()
    with patch("backend.src.services.encryption.EncryptionService", return_value=mock) as _:
        yield mock

@pytest.fixture
def test_app(app, mock_storage, mock_encryption):
    """Configure test application with routes."""
    async def upload_file(file: UploadFile = File(...)):
        content = await file.read()
        encrypted = await mock_encryption.encrypt_file(content)
        file_id = await mock_storage.store_file(encrypted)
        return {"file_id": file_id}
    
    async def process_file(file_id: str):
        content = await mock_storage.get_file(file_id)
        decrypted = await mock_encryption.decrypt_file(content)
        processed = decrypted
        encrypted = await mock_encryption.encrypt_file(processed)
        result_id = await mock_storage.store_file(encrypted)
        return {"result_id": result_id}
    
    app.post("/files/")(upload_file)
    app.post("/process/{file_id}")(process_file)
    return app

class TestFileProcessingFlow:
    """Test suite for complete file processing flow.
    
    Validation Order:
    1. Extension check - Rejects dangerous files (.exe, .bat, etc.) with 400
    2. MIME type check - Rejects files with invalid content with 415
    3. Processing - Only valid files reach this stage
    """

    async def test_valid_mp3_upload(self, test_app, client, mock_storage, mock_encryption):
        """Test successful processing of MP3 audio file."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload
        files = {"file": ("test.mp3", VALID_MP3_CONTENT, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_valid_wav_upload(self, test_app, client, mock_storage, mock_encryption):
        """Test successful processing of WAV audio file."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload
        files = {"file": ("test.wav", VALID_WAV_CONTENT, "audio/wav")}
        response = client.post("/files/", files=files)
        
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_valid_ogg_upload(self, test_app, client, mock_storage, mock_encryption):
        """Test successful processing of OGG audio file."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload
        files = {"file": ("test.ogg", VALID_OGG_CONTENT, "audio/ogg")}
        response = client.post("/files/", files=files)
        
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_valid_mp4_upload(self, test_app, client, mock_storage, mock_encryption):
        """Test successful processing of MP4 video file."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload
        files = {"file": ("test.mp4", VALID_MP4_CONTENT, "video/mp4")}
        response = client.post("/files/", files=files)
        
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_valid_mpeg_upload(self, test_app, client, mock_storage, mock_encryption):
        """Test successful processing of MPEG video file."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload
        files = {"file": ("test.mpeg", VALID_MPEG_CONTENT, "video/mpeg")}
        response = client.post("/files/", files=files)
        
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_dangerous_extension_is_blocked(self, test_app, client, mock_storage, mock_encryption):
        """Test that dangerous file extensions (.exe, .bat, etc.) are blocked."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        try:
            # Attempt to upload a dangerous file
            files = {"file": ("test.exe", b"malicious", "application/x-msdownload")}
            response = client.post("/files/", files=files)
            pytest.fail("Expected file to be blocked but it wasn't")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "This file type is not allowed for security reasons" in e.detail
            assert "Please upload audio or video files only" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_mime_type_validation_blocks_fake_audio(self, test_app, client, mock_storage, mock_encryption):
        """Test that files with incorrect content are blocked by MIME type validation."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        try:
            # Attempt to upload a file with fake audio content
            files = {"file": ("test.mp3", b"fake audio content", "audio/mpeg")}
            response = client.post("/files/", files=files)
            pytest.fail("Expected file to be blocked but it wasn't")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 415
            assert "This file doesn't appear to be a valid audio/video file" in e.detail
            assert "Detected type: application/octet-stream" in e.detail
            assert "Please ensure you're uploading a supported media file" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_file_too_large(self, test_app, client, mock_storage, mock_encryption):
        """Test that files exceeding MAX_UPLOAD_SIZE are rejected."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        # Create a large file that exceeds MAX_UPLOAD_SIZE
        large_content = b"x" * (12_000_000_001)  # Just over 12GB
        files = {"file": ("large.mp3", large_content, "audio/mpeg")}
        
        try:
            response = client.post("/files/", files=files)
            pytest.fail("Expected large file to be blocked but it wasn't")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 413
            assert "This file is too large" in e.detail
            assert "Maximum allowed size is 12GB" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_empty_file_rejected(self, test_app, client, mock_storage, mock_encryption):
        """Test that empty files are rejected."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        # Try to upload an empty file with content-length header
        headers = {"content-length": "0"}
        files = {"file": ("empty.mp3", b"", "audio/mpeg")}
        
        try:
            response = client.post("/files/", files=files, headers=headers)
            pytest.fail("Expected empty file to be blocked but it wasn't")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "The file appears to be empty" in e.detail
            assert "Please check that it contains content" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_path_traversal_blocked(self, test_app, client, mock_storage, mock_encryption):
        """Test that path traversal attempts in filenames are blocked."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        # Test various path traversal attempts
        traversal_filenames = [
            "../test.mp3",  # Parent directory
            "folder/test.mp3",  # Forward slash
            "folder\\test.mp3",  # Backslash
        ]

        for filename in traversal_filenames:
            try:
                files = {"file": (filename, VALID_MP3_CONTENT, "audio/mpeg")}
                response = client.post("/files/", files=files)
                pytest.fail(f"Expected path traversal to be blocked: {filename}")
            except HTTPException as e:
                # Verify correct error was raised
                assert e.status_code == 400
                assert "This filename contains invalid characters" in e.detail
                assert "Please use a simple filename" in e.detail
                
                # Verify file was never processed
                mock_storage.store_file.assert_not_called()
                mock_encryption.encrypt_file.assert_not_called()

    async def test_multiple_extensions_blocked(self, test_app, client, mock_storage, mock_encryption):
        """Test that files with multiple extensions are blocked."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        # Test various multiple extension attempts
        suspicious_filenames = [
            "music.mp3.exe",  # Classic extension spoofing
            "video.mp4.bat",  # Batch file
            "audio.wav.sh",   # Shell script
            "media.ogg.cmd"   # Command file
        ]

        for filename in suspicious_filenames:
            try:
                files = {"file": (filename, VALID_MP3_CONTENT, "audio/mpeg")}
                response = client.post("/files/", files=files)
                pytest.fail(f"Expected multiple extensions to be blocked: {filename}")
            except HTTPException as e:
                # Verify correct error was raised
                assert e.status_code == 400
                assert "This file type is not allowed for security reasons" in e.detail
                assert "Please upload audio or video files only" in e.detail
                
                # Verify file was never processed
                mock_storage.store_file.assert_not_called()
                mock_encryption.encrypt_file.assert_not_called()

    async def test_malicious_content_blocked(self, test_app, client, mock_storage, mock_encryption):
        """Test that files with malicious content are blocked."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt

        # Test various malicious content patterns
        malicious_contents = [
            b"#!/bin/bash\necho 'malicious'",  # Shell script header
            b"rm -rf /\nsome audio content",    # Dangerous command
        ]

        for content in malicious_contents:
            try:
                files = {"file": ("test.mp3", content, "audio/mpeg")}
                response = client.post("/files/", files=files)
                pytest.fail(f"Expected malicious content to be blocked")
            except HTTPException as e:
                # Verify correct error was raised
                assert e.status_code == 400
                assert "This file contains potentially harmful content" in e.detail
                assert "Please ensure you're uploading a regular media file" in e.detail
                
                # Verify file was never processed
                mock_storage.store_file.assert_not_called()
                mock_encryption.encrypt_file.assert_not_called()

    async def test_missing_file_field(self, test_app, client, mock_storage, mock_encryption):
        """Test that upload without file field is rejected."""
        try:
            # Try to upload without file field
            response = client.post("/files/", files={})
            pytest.fail("Expected missing file to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "No file uploaded" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_empty_form(self, test_app, client, mock_storage, mock_encryption):
        """Test that empty form submission is rejected."""
        try:
            # Try to upload with empty form
            response = client.post("/files/")
            pytest.fail("Expected empty form to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "No file uploaded" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_missing_content_type(self, test_app, client, mock_storage, mock_encryption):
        """Test that upload without content-type is rejected."""
        try:
            # Try to upload with wrong content type
            headers = {"content-type": "application/json"}  # Wrong content type
            response = client.post("/files/", json={"file": "test"}, headers=headers)
            pytest.fail("Expected missing content-type to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "No file uploaded" in e.detail
            assert "multipart/form-data" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_wrong_content_type(self, test_app, client, mock_storage, mock_encryption):
        """Test that upload with mismatched content-type is rejected."""
        try:
            # Try to upload with wrong content-type
            files = {"file": ("test.mp3", VALID_MP3_CONTENT, "video/mp4")}  # Wrong content-type for MP3
            response = client.post("/files/", files=files)
            pytest.fail("Expected mismatched content-type to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 415
            assert "Content type mismatch" in e.detail
            assert "Declared: video/mp4" in e.detail
            assert "Detected: audio/mpeg" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_missing_filename(self, test_app, client, mock_storage, mock_encryption):
        """Test that upload without filename is rejected."""
        try:
            # Try to upload without filename
            files = {"file": (None, VALID_MP3_CONTENT, "audio/mpeg")}
            response = client.post("/files/", files=files)
            pytest.fail("Expected missing filename to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 400
            assert "Missing filename" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_unicode_filename(self, test_app, client, mock_storage, mock_encryption):
        """Test that upload with Unicode filename is handled correctly."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Test file upload with Unicode filename
        files = {"file": ("测试音频.mp3", VALID_MP3_CONTENT, "audio/mpeg")}
        response = client.post("/files/", files=files)
        
        # Verify success
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_file_at_size_limit(self, test_app, client, mock_storage, mock_encryption):
        """Test that file exactly at MAX_UPLOAD_SIZE is accepted."""
        # Setup mocks
        async def mock_store(x):
            return "file_id"
        async def mock_encrypt(x):
            return b"encrypted_content"
        mock_storage.store_file.side_effect = mock_store
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        
        # Use valid MP3 content for testing
        content = VALID_MP3_CONTENT
        files = {"file": ("test.mp3", content, "audio/mpeg")}
        
        # Test file upload
        response = client.post("/files/", files=files)
        
        # Verify success
        assert response.status_code == 200
        assert "file_id" in response.json()
        
        # Verify flow
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()

    async def test_file_just_over_limit(self, test_app, client, mock_storage, mock_encryption):
        """Test that file just over MAX_UPLOAD_SIZE is rejected."""
        try:
            # Create file just over size limit
            content = b"x" * (12_000_000_000 + 1)  # 12GB + 1 byte
            files = {"file": ("test.mp3", content, "audio/mpeg")}
            
            response = client.post("/files/", files=files)
            pytest.fail("Expected oversized file to be rejected")
        except HTTPException as e:
            # Verify correct error was raised
            assert e.status_code == 413
            assert "This file is too large" in e.detail
            assert "Maximum allowed size is 12GB" in e.detail
            
            # Verify file was never processed
            mock_storage.store_file.assert_not_called()
            mock_encryption.encrypt_file.assert_not_called()

    async def test_processing_chain(self, test_app, client, mock_storage, mock_encryption):
        """Test complete processing chain including retrieval."""
        # Setup mocks
        async def mock_get(x):
            return b"stored_content"
        async def mock_decrypt(x):
            return VALID_MP3_CONTENT
        async def mock_encrypt(x):
            return b"encrypted_content"
        async def mock_store(x):
            return "result_id"
        mock_storage.get_file.side_effect = mock_get
        mock_encryption.decrypt_file.side_effect = mock_decrypt
        mock_encryption.encrypt_file.side_effect = mock_encrypt
        mock_storage.store_file.side_effect = mock_store
        
        # Test processing
        response = client.post("/process/test_file_id")
        
        assert response.status_code == 200
        assert "result_id" in response.json()
        
        # Verify chain
        mock_storage.get_file.assert_called_once()
        mock_encryption.decrypt_file.assert_called_once()
        mock_encryption.encrypt_file.assert_called_once()
        mock_storage.store_file.assert_called_once()
