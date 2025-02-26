"""Custom exceptions for the application."""

from typing import Optional, Dict, Any
from ..types import ErrorContext

class TranscriboError(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None,
        status_code: int = 500
    ) -> None:
        """Initialize exception.
        
        Args:
            message: Error message
            details: Optional error context
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.details = details
        self.status_code = status_code

class ConfigurationError(TranscriboError):
    """Raised when there is a configuration error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class ValidationError(TranscriboError):
    """Raised when validation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=400)

class AuthenticationError(TranscriboError):
    """Raised when authentication fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=401)

class AuthorizationError(TranscriboError):
    """Raised when authorization fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=403)

class ResourceNotFoundError(TranscriboError):
    """Raised when a resource is not found."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=404)

class ConflictError(TranscriboError):
    """Raised when there is a conflict with existing data."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=409)

class DependencyError(TranscriboError):
    """Raised when there is a dependency error."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class ServiceError(TranscriboError):
    """Raised when a service operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class DatabaseError(TranscriboError):
    """Raised when a database operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class StorageError(TranscriboError):
    """Raised when a storage operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class FileError(TranscriboError):
    """Raised when a file operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class EditorError(TranscriboError):
    """Raised when an editor operation fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class RouteError(TranscriboError):
    """Raised when a route handler fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class HashVerificationError(TranscriboError):
    """Raised when hash verification fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=400)

class ZipError(TranscriboError):
    """Raised when ZIP processing fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=400)

class TranscriptionError(TranscriboError):
    """Raised when transcription fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class EncryptionError(TranscriboError):
    """Raised when encryption/decryption fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class KeyManagementError(TranscriboError):
    """Raised when key management fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)

class JobError(TranscriboError):
    """Raised when job management fails."""
    
    def __init__(
        self,
        message: str,
        details: Optional[ErrorContext] = None
    ) -> None:
        super().__init__(message, details, status_code=500)
