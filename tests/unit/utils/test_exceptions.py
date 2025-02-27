"""Tests for custom exceptions."""

import pytest
from datetime import datetime

from src.utils.exceptions import (
    TranscriboError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    StorageError,
    TranscriptionError,
    DatabaseError,
    ZipError,
    EncryptionError,
    KeyManagementError,
    QuotaExceededError,
    TokenError,
    TokenExpiredError,
    TokenInvalidError,
    TokenMissingError
)
from src.types import ErrorCode, ErrorSeverity

def test_transcribo_error():
    """Test base error class."""
    error = TranscriboError(
        message="Test error",
        code=ErrorCode.INTERNAL_ERROR,
        severity=ErrorSeverity.ERROR,
        details={"test": "details"},
        is_retryable=True,
        retry_after=60
    )
    
    assert str(error) == "Test error"
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"test": "details"}
    assert error.is_retryable is True
    assert error.retry_after == 60

def test_validation_error():
    """Test validation error."""
    error = ValidationError(
        message="Invalid input",
        details={"field": "test"}
    )
    
    assert str(error) == "Invalid input"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.severity == ErrorSeverity.WARNING
    assert error.details == {"field": "test"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_authentication_error():
    """Test authentication error."""
    error = AuthenticationError(
        message="Invalid token",
        details={"token": "expired"}
    )
    
    assert str(error) == "Invalid token"
    assert error.code == ErrorCode.AUTHENTICATION_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"token": "expired"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_authorization_error():
    """Test authorization error."""
    error = AuthorizationError(
        message="Insufficient permissions",
        details={"required": "admin"}
    )
    
    assert str(error) == "Insufficient permissions"
    assert error.code == ErrorCode.AUTHORIZATION_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"required": "admin"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_resource_not_found_error():
    """Test resource not found error."""
    error = ResourceNotFoundError(
        message="File not found",
        details={"path": "/test.txt"}
    )
    
    assert str(error) == "File not found"
    assert error.code == ErrorCode.RESOURCE_NOT_FOUND
    assert error.severity == ErrorSeverity.WARNING
    assert error.details == {"path": "/test.txt"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_storage_error():
    """Test storage error."""
    error = StorageError(
        message="Storage unavailable",
        details={"service": "minio"},
        is_retryable=True,
        retry_after=60
    )
    
    assert str(error) == "Storage unavailable"
    assert error.code == ErrorCode.STORAGE_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"service": "minio"}
    assert error.is_retryable is True
    assert error.retry_after == 60

def test_transcription_error():
    """Test transcription error."""
    error = TranscriptionError(
        message="Transcription failed",
        details={"model": "whisper"},
        is_retryable=True,
        retry_after=300
    )
    
    assert str(error) == "Transcription failed"
    assert error.code == ErrorCode.TRANSCRIPTION_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"model": "whisper"}
    assert error.is_retryable is True
    assert error.retry_after == 300

def test_database_error():
    """Test database error."""
    error = DatabaseError(
        message="Connection failed",
        details={"host": "localhost"},
        is_retryable=True,
        retry_after=30
    )
    
    assert str(error) == "Connection failed"
    assert error.code == ErrorCode.DATABASE_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"host": "localhost"}
    assert error.is_retryable is True
    assert error.retry_after == 30

def test_zip_error():
    """Test ZIP error."""
    error = ZipError(
        message="Invalid ZIP file",
        details={"file": "test.zip"}
    )
    
    assert str(error) == "Invalid ZIP file"
    assert error.code == ErrorCode.ZIP_ERROR
    assert error.severity == ErrorSeverity.WARNING
    assert error.details == {"file": "test.zip"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_encryption_error():
    """Test encryption error."""
    error = EncryptionError(
        message="Encryption failed",
        details={"algorithm": "AES"}
    )
    
    assert str(error) == "Encryption failed"
    assert error.code == ErrorCode.ENCRYPTION_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"algorithm": "AES"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_key_management_error():
    """Test key management error."""
    error = KeyManagementError(
        message="Key rotation failed",
        details={"key_id": "test"},
        is_retryable=True,
        retry_after=60
    )
    
    assert str(error) == "Key rotation failed"
    assert error.code == ErrorCode.KEY_MANAGEMENT_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"key_id": "test"}
    assert error.is_retryable is True
    assert error.retry_after == 60

def test_quota_exceeded_error():
    """Test quota exceeded error."""
    error = QuotaExceededError(
        message="API quota exceeded",
        details={"limit": 1000},
        retry_after=3600
    )
    
    assert str(error) == "API quota exceeded"
    assert error.code == ErrorCode.QUOTA_EXCEEDED
    assert error.severity == ErrorSeverity.WARNING
    assert error.details == {"limit": 1000}
    assert error.is_retryable is True
    assert error.retry_after == 3600

def test_quota_exceeded_error_no_retry():
    """Test quota exceeded error without retry."""
    error = QuotaExceededError(
        message="API quota exceeded",
        details={"limit": 1000}
    )
    
    assert error.is_retryable is False
    assert error.retry_after is None

def test_token_error():
    """Test base token error."""
    error = TokenError(
        message="Token error",
        code=ErrorCode.TOKEN_INVALID,
        details={"token": "test"}
    )
    
    assert str(error) == "Token error"
    assert error.code == ErrorCode.TOKEN_INVALID
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"token": "test"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_token_expired_error():
    """Test token expired error."""
    error = TokenExpiredError(
        message="Token expired",
        details={"expiry": "2025-01-01"}
    )
    
    assert str(error) == "Token expired"
    assert error.code == ErrorCode.TOKEN_EXPIRED
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"expiry": "2025-01-01"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_token_invalid_error():
    """Test token invalid error."""
    error = TokenInvalidError(
        message="Invalid signature",
        details={"reason": "signature"}
    )
    
    assert str(error) == "Invalid signature"
    assert error.code == ErrorCode.TOKEN_INVALID
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"reason": "signature"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_token_missing_error():
    """Test token missing error."""
    error = TokenMissingError(
        message="Token not provided",
        details={"header": "Authorization"}
    )
    
    assert str(error) == "Token not provided"
    assert error.code == ErrorCode.TOKEN_MISSING
    assert error.severity == ErrorSeverity.ERROR
    assert error.details == {"header": "Authorization"}
    assert error.is_retryable is False
    assert error.retry_after is None

def test_error_inheritance():
    """Test error class inheritance."""
    error = ValidationError("Test error")
    
    assert isinstance(error, ValidationError)
    assert isinstance(error, TranscriboError)
    assert isinstance(error, Exception)

def test_error_details_default():
    """Test error details default value."""
    error = TranscriboError("Test error")
    
    assert error.details == {}

def test_error_retry_default():
    """Test error retry defaults."""
    error = TranscriboError("Test error")
    
    assert error.is_retryable is False
    assert error.retry_after is None
