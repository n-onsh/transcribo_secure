"""Custom exception classes."""

from typing import Optional, Dict, Any
from datetime import datetime
from ..types import ErrorContext

class TranscriboError(Exception):
    """Base exception class for application errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None,
        status_code: int = 500
    ) -> None:
        """Initialize exception.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message: str = message
        self.details: ErrorContext = details or {
            "timestamp": datetime.utcnow(),
            "details": {}
        }
        self.help_url: Optional[str] = help_url
        self.status_code: int = status_code
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary.
        
        Returns:
            Dictionary representation of error
        """
        return {
            "code": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
            "help_url": self.help_url,
            "status_code": self.status_code
        }

class ValidationError(TranscriboError):
    """Raised when input validation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize validation error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/validation",
            status_code=400
        )

class AuthenticationError(TranscriboError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize authentication error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/authentication",
            status_code=401
        )

class AuthorizationError(TranscriboError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize authorization error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/authorization",
            status_code=403
        )

class ResourceNotFoundError(TranscriboError):
    """Raised when a requested resource is not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize not found error.
        
        Args:
            resource_type: Type of resource that was not found
            resource_id: ID of resource that was not found
            details: Additional error details
            help_url: URL to documentation about this error
        """
        message = f"{resource_type.title()} with ID {resource_id} not found"
        error_details: ErrorContext = {
            "operation": "get_resource",
            "resource_id": resource_id,
            "resource_type": resource_type,
            "timestamp": datetime.utcnow(),
            "details": details["details"] if details else {}
        }
        super().__init__(
            message,
            error_details,
            help_url or "https://docs.transcribo.io/errors/not-found",
            status_code=404
        )

class ConflictError(TranscriboError):
    """Raised when there is a conflict with existing data."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize conflict error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/conflict",
            status_code=409
        )

class RateLimitError(TranscriboError):
    """Raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str,
        retry_after: int,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize rate limit error.
        
        Args:
            message: Error message
            retry_after: Seconds until retry is allowed
            details: Additional error details
            help_url: URL to documentation about this error
        """
        error_details: ErrorContext = {
            "operation": "rate_limit_check",
            "timestamp": datetime.utcnow(),
            "details": {
                "retry_after": retry_after,
                **(details["details"] if details else {})
            }
        }
        super().__init__(
            message,
            error_details,
            help_url or "https://docs.transcribo.io/errors/rate-limit",
            status_code=429
        )

class DatabaseError(TranscriboError):
    """Raised when a database operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize database error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/database",
            status_code=500
        )

class StorageError(TranscriboError):
    """Raised when a storage operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize storage error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/storage",
            status_code=500
        )

class TranscriptionError(TranscriboError):
    """Raised when transcription processing fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize transcription error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/transcription",
            status_code=500
        )

class ConfigurationError(TranscriboError):
    """Raised when there is a configuration error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        help_url: Optional[str] = None
    ) -> None:
        """Initialize configuration error.
        
        Args:
            message: Error message
            details: Additional error details
            help_url: URL to documentation about this error
        """
        super().__init__(
            message,
            details,
            help_url or "https://docs.transcribo.io/errors/configuration",
            status_code=500
        )
