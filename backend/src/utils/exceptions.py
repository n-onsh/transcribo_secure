"""Custom exceptions for the application."""

from typing import Dict, Any, Optional
from datetime import datetime
from ..types import ErrorCode, ErrorSeverity

class TranscriboError(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = False,
        retry_after: Optional[int] = None
    ):
        """Initialize exception.
        
        Args:
            message: Error message
            code: Error code
            severity: Error severity level
            details: Optional error details
            is_retryable: Whether the operation can be retried
            retry_after: Optional seconds to wait before retry
        """
        super().__init__(message)
        self.code = code
        self.severity = severity
        self.details = details or {}
        self.is_retryable = is_retryable
        self.retry_after = retry_after

class ValidationError(TranscriboError):
    """Validation error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize validation error.
        
        Args:
            message: Error message
            details: Optional validation details
        """
        super().__init__(
            message,
            code=ErrorCode.VALIDATION_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details
        )

class AuthenticationError(TranscriboError):
    """Authentication error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize authentication error.
        
        Args:
            message: Error message
            details: Optional authentication details
        """
        super().__init__(
            message,
            code=ErrorCode.AUTHENTICATION_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details
        )

class AuthorizationError(TranscriboError):
    """Authorization error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize authorization error.
        
        Args:
            message: Error message
            details: Optional authorization details
        """
        super().__init__(
            message,
            code=ErrorCode.AUTHORIZATION_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details
        )

class ResourceNotFoundError(TranscriboError):
    """Resource not found error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize not found error.
        
        Args:
            message: Error message
            details: Optional resource details
        """
        super().__init__(
            message,
            code=ErrorCode.RESOURCE_NOT_FOUND,
            severity=ErrorSeverity.WARNING,
            details=details
        )

class StorageError(TranscriboError):
    """Storage service error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = True,
        retry_after: Optional[int] = 60
    ):
        """Initialize storage error.
        
        Args:
            message: Error message
            details: Optional storage details
            is_retryable: Whether operation can be retried
            retry_after: Seconds to wait before retry
        """
        super().__init__(
            message,
            code=ErrorCode.STORAGE_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            is_retryable=is_retryable,
            retry_after=retry_after
        )

class TranscriptionError(TranscriboError):
    """Transcription service error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = True,
        retry_after: Optional[int] = 300
    ):
        """Initialize transcription error.
        
        Args:
            message: Error message
            details: Optional transcription details
            is_retryable: Whether operation can be retried
            retry_after: Seconds to wait before retry
        """
        super().__init__(
            message,
            code=ErrorCode.TRANSCRIPTION_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            is_retryable=is_retryable,
            retry_after=retry_after
        )

class DatabaseError(TranscriboError):
    """Database error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = True,
        retry_after: Optional[int] = 30
    ):
        """Initialize database error.
        
        Args:
            message: Error message
            details: Optional database details
            is_retryable: Whether operation can be retried
            retry_after: Seconds to wait before retry
        """
        super().__init__(
            message,
            code=ErrorCode.DATABASE_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            is_retryable=is_retryable,
            retry_after=retry_after
        )

class ZipError(TranscriboError):
    """ZIP file error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize ZIP error.
        
        Args:
            message: Error message
            details: Optional ZIP details
        """
        super().__init__(
            message,
            code=ErrorCode.ZIP_ERROR,
            severity=ErrorSeverity.WARNING,
            details=details
        )

class EncryptionError(TranscriboError):
    """Encryption error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize encryption error.
        
        Args:
            message: Error message
            details: Optional encryption details
        """
        super().__init__(
            message,
            code=ErrorCode.ENCRYPTION_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details
        )

class KeyManagementError(TranscriboError):
    """Key management error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        is_retryable: bool = True,
        retry_after: Optional[int] = 60
    ):
        """Initialize key management error.
        
        Args:
            message: Error message
            details: Optional key management details
            is_retryable: Whether operation can be retried
            retry_after: Seconds to wait before retry
        """
        super().__init__(
            message,
            code=ErrorCode.KEY_MANAGEMENT_ERROR,
            severity=ErrorSeverity.ERROR,
            details=details,
            is_retryable=is_retryable,
            retry_after=retry_after
        )

class QuotaExceededError(TranscriboError):
    """Quota exceeded error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None
    ):
        """Initialize quota exceeded error.
        
        Args:
            message: Error message
            details: Optional quota details
            retry_after: Optional seconds until quota resets
        """
        super().__init__(
            message,
            code=ErrorCode.QUOTA_EXCEEDED,
            severity=ErrorSeverity.WARNING,
            details=details,
            is_retryable=retry_after is not None,
            retry_after=retry_after
        )

class TokenError(TranscriboError):
    """Token error base class."""
    
    def __init__(
        self,
        message: str,
        code: ErrorCode,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize token error.
        
        Args:
            message: Error message
            code: Specific token error code
            details: Optional token details
        """
        super().__init__(
            message,
            code=code,
            severity=ErrorSeverity.ERROR,
            details=details
        )

class TokenExpiredError(TokenError):
    """Token expired error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize token expired error.
        
        Args:
            message: Error message
            details: Optional token details
        """
        super().__init__(
            message,
            code=ErrorCode.TOKEN_EXPIRED,
            details=details
        )

class TokenInvalidError(TokenError):
    """Token invalid error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize token invalid error.
        
        Args:
            message: Error message
            details: Optional token details
        """
        super().__init__(
            message,
            code=ErrorCode.TOKEN_INVALID,
            details=details
        )

class TokenMissingError(TokenError):
    """Token missing error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Initialize token missing error.
        
        Args:
            message: Error message
            details: Optional token details
        """
        super().__init__(
            message,
            code=ErrorCode.TOKEN_MISSING,
            details=details
        )
