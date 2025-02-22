"""
Unit Test Suite for File Validation Middleware

This test suite verifies the file validation middleware that ensures secure
and correct file handling in the application. It follows the test plan's
core principles of focusing on security and reliability.

Test Categories:
1. Basic Validation
   - MIME type verification
   - File size checks
   - Empty file detection
   - Format validation

2. Security Checks
   - Path traversal prevention
   - Extension spoofing detection
   - Malicious content detection
   - File content validation

3. Error Handling
   - 400 Bad Request (invalid files)
   - 413 Payload Too Large (size limits)
   - 415 Unsupported Media Type (MIME types)

Integration Notes:
- These unit tests focus on the middleware in isolation
- For complete validation testing, see:
  * integration/flows/test_file_processing.py (validation in processing chain)
  * e2e/critical/test_user_flows.py (validation in user workflows)

Test Environment:
- Uses pytest fixtures for request mocking
- Mocks python-magic for MIME type detection
- Simulates multipart form data
- Uses test data constants for file content

Usage:
    pytest tests/unit/security/test_file_validation.py -v
    pytest tests/unit/security/test_file_validation.py -k "test_security"
    pytest tests/unit/security/test_file_validation.py --cov
"""
import pytest
from fastapi import UploadFile, Request, HTTPException
from unittest.mock import MagicMock, patch, AsyncMock
from backend.src.middleware.file_validation import validate_file_middleware
import io
import magic.magic as magic

# Test data
VALID_MP3_HEADER = b"ID3\x04\x00\x00\x00\x00\x00\x00" + b"\x00" * 1024
VALID_WAV_HEADER = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 1024
INVALID_FILE = b"not an audio file" * 1024

@pytest.fixture
def mock_request():
    """Create a mock request with configurable content."""
    request = MagicMock()
    request.method = "POST"
    request.url.path = "/files/"
    
    # Make receive a coroutine
    request.receive = AsyncMock()
    
    return request

@pytest.fixture
def mock_call_next():
    """Create a mock for the call_next function."""
    return AsyncMock()

class TestFileValidation:
    """Test suite for file validation middleware."""

    async def test_valid_mp3_file(self, mock_request, mock_call_next, test_env):
        """Test validation of valid MP3 file."""
        # Mock file content
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.mp3"\r\n'
                b'Content-Type: audio/mpeg\r\n\r\n'
            ) + VALID_MP3_HEADER + b'\r\n--boundary--\r\n'
        }
        
        # Mock python-magic to detect MP3
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "audio/mpeg"
            
            # Run middleware
            await validate_file_middleware(mock_request, mock_call_next)
            
            # Verify call_next was called
            mock_call_next.assert_called_once()

    async def test_valid_wav_file(self, mock_request, mock_call_next, test_env):
        """Test validation of valid WAV file."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.wav"\r\n'
                b'Content-Type: audio/wav\r\n\r\n'
            ) + VALID_WAV_HEADER + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "audio/wav"
            
            await validate_file_middleware(mock_request, mock_call_next)
            mock_call_next.assert_called_once()

    async def test_invalid_mime_type(self, mock_request, mock_call_next, test_env):
        """Test rejection of invalid MIME types."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.file"\r\n'
                b'Content-Type: application/octet-stream\r\n\r\n'
            ) + INVALID_FILE + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "text/plain"
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_file_middleware(mock_request, mock_call_next)
                await mock_request._receive()
            
            assert exc_info.value.status_code == 415  # Unsupported Media Type
            mock_call_next.assert_not_called()

    async def test_file_size_limit(self, mock_request, mock_call_next, test_env):
        """Test file size validation."""
        # Set content length over limit
        mock_request.headers = {"content-length": str(13_000_000_000)}  # > 12GB
        
        with pytest.raises(HTTPException) as exc_info:
            await validate_file_middleware(mock_request, mock_call_next)
        
        assert exc_info.value.status_code == 413  # Payload Too Large
        mock_call_next.assert_not_called()

    @pytest.mark.parametrize("mime_type,should_pass", [
        ("audio/mpeg", True),
        ("audio/wav", True),
        ("audio/ogg", True),
        ("video/mp4", True),
        ("video/mpeg", True),
        ("text/plain", False),
        ("application/pdf", False),
        ("image/jpeg", False),
    ])
    async def test_mime_type_validation(self, mock_request, mock_call_next, test_env, mime_type, should_pass):
        """Test validation of various MIME types."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.file"\r\n'
                b'Content-Type: application/octet-stream\r\n\r\n'
            ) + b"test content" + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = mime_type
            
            if should_pass:
                await validate_file_middleware(mock_request, mock_call_next)
                mock_call_next.assert_called_once()
            else:
                with pytest.raises(HTTPException) as exc_info:
                    await validate_file_middleware(mock_request, mock_call_next)
                    await mock_request._receive()
                assert exc_info.value.status_code == 415
                mock_call_next.assert_not_called()

    async def test_non_file_request(self, mock_request, mock_call_next):
        """Test that non-file requests pass through."""
        # Change path to non-file endpoint
        mock_request.url.path = "/api/status"
        
        await validate_file_middleware(mock_request, mock_call_next)
        mock_call_next.assert_called_once()

    async def test_non_post_request(self, mock_request, mock_call_next):
        """Test that non-POST requests pass through."""
        mock_request.method = "GET"
        
        await validate_file_middleware(mock_request, mock_call_next)
        mock_call_next.assert_called_once()

    async def test_malformed_file(self, mock_request, mock_call_next, test_env):
        """Test handling of malformed files."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.file"\r\n'
                b'Content-Type: application/octet-stream\r\n\r\n'
            ) + b"malformed content" + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            # Return an invalid MIME type
            mock_magic.return_value.from_buffer.return_value = "application/octet-stream"
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_file_middleware(mock_request, mock_call_next)
                await mock_request._receive()
            
            assert exc_info.value.status_code == 415  # Unsupported Media Type
            assert exc_info.value.detail == "Unsupported file type: application/octet-stream"  # Verify error message
            mock_call_next.assert_not_called()

    async def test_empty_file(self, mock_request, mock_call_next, test_env):
        """Test handling of empty files."""
        # Setup request for file upload endpoint
        mock_request.method = "POST"
        mock_request.url.path = "/files/"
        mock_request.headers = {"content-length": "0"}
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.file"\r\n'
                b'Content-Type: application/octet-stream\r\n\r\n'
                b'\r\n--boundary--\r\n'
            )
        }
        
        # Call middleware and expect exception
        with pytest.raises(HTTPException) as exc_info:
            await validate_file_middleware(mock_request, mock_call_next)
            # Trigger the receive wrapper
            await mock_request._receive()
        
        assert exc_info.value.status_code == 400  # Bad Request
        assert exc_info.value.detail == "Empty file"  # Verify error message
        mock_call_next.assert_not_called()

    async def test_multipart_handling(self, mock_request, mock_call_next, test_env):
        """Test handling of multipart form data."""
        # Simulate multipart form data with file
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.mp3"\r\n'
                b'Content-Type: audio/mpeg\r\n\r\n'
            ) + VALID_MP3_HEADER + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "audio/mpeg"
            
            await validate_file_middleware(mock_request, mock_call_next)
            mock_call_next.assert_called_once()

    async def test_path_traversal_attempt(self, mock_request, mock_call_next, test_env):
        """Test rejection of path traversal attempts in filenames."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="../../../etc/passwd"\r\n'
                b'Content-Type: audio/mpeg\r\n\r\n'
            ) + VALID_MP3_HEADER + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "audio/mpeg"
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_file_middleware(mock_request, mock_call_next)
                await mock_request._receive()
            
            assert exc_info.value.status_code == 400  # Bad Request
            assert exc_info.value.detail == "Invalid filename"  # Verify error message
            mock_call_next.assert_not_called()

    async def test_extension_spoofing(self, mock_request, mock_call_next, test_env):
        """Test detection of file extension spoofing."""
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="malicious.mp3.exe"\r\n'
                b'Content-Type: audio/mpeg\r\n\r\n'
            ) + VALID_MP3_HEADER + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "audio/mpeg"
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_file_middleware(mock_request, mock_call_next)
                await mock_request._receive()
            
            assert exc_info.value.status_code == 400  # Bad Request
            assert exc_info.value.detail == "Invalid filename"  # Verify error message
            mock_call_next.assert_not_called()

    async def test_malicious_content(self, mock_request, mock_call_next, test_env):
        """Test rejection of potentially malicious file content."""
        # Create a file that looks like an MP3 but contains suspicious patterns
        malicious_content = VALID_MP3_HEADER + b"#!/bin/bash\nrm -rf /\n"
        
        mock_request.receive.return_value = {
            "type": "http.request",
            "body": (
                b'--boundary\r\n'
                b'Content-Disposition: form-data; name="file"; filename="test.mp3"\r\n'
                b'Content-Type: audio/mpeg\r\n\r\n'
            ) + malicious_content + b'\r\n--boundary--\r\n'
        }
        
        with patch("magic.magic.Magic") as mock_magic:
            mock_magic.return_value.from_buffer.return_value = "text/x-shellscript"
            
            with pytest.raises(HTTPException) as exc_info:
                await validate_file_middleware(mock_request, mock_call_next)
                await mock_request._receive()
            
            assert exc_info.value.status_code == 415  # Unsupported Media Type
            assert exc_info.value.detail == "Unsupported file type: text/x-shellscript"
            mock_call_next.assert_not_called()
