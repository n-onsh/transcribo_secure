from typing import Optional, Dict, Any
from fastapi import HTTPException
from ..models.base import ErrorResponse

class TranscriboError(HTTPException):
    """Base exception class for Transcribo application"""
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status_code,
            detail=ErrorResponse(
                code=code,
                message=message,
                details=details
            ).dict()
        )

class ValidationError(TranscriboError):
    """Raised when input validation fails"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=400,
            code="VALIDATION_ERROR",
            message=message,
            details=details
        )

class AuthenticationError(TranscriboError):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            status_code=401,
            code="AUTHENTICATION_ERROR",
            message=message
        )

class AuthorizationError(TranscriboError):
    """Raised when user lacks permission"""
    def __init__(self, message: str = "Permission denied"):
        super().__init__(
            status_code=403,
            code="AUTHORIZATION_ERROR",
            message=message
        )

class ResourceNotFoundError(TranscriboError):
    """Raised when requested resource is not found"""
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message=f"{resource_type} not found: {resource_id}",
            details={
                "resource_type": resource_type,
                "resource_id": resource_id
            }
        )

class ResourceConflictError(TranscriboError):
    """Raised when resource state conflicts with request"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=409,
            code="RESOURCE_CONFLICT",
            message=message,
            details=details
        )

class RateLimitError(TranscriboError):
    """Raised when rate limit is exceeded"""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        details = {"retry_after": retry_after} if retry_after else None
        super().__init__(
            status_code=429,
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            details=details
        )

class StorageError(TranscriboError):
    """Raised when storage operations fail"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            code="STORAGE_ERROR",
            message=message,
            details=details
        )

class TranscriptionError(TranscriboError):
    """Raised when transcription processing fails"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            code="TRANSCRIPTION_ERROR",
            message=message,
            details=details
        )

class DatabaseError(TranscriboError):
    """Raised when database operations fail"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            code="DATABASE_ERROR",
            message=message,
            details=details
        )

class ConfigurationError(TranscriboError):
    """Raised when there are configuration issues"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=500,
            code="CONFIGURATION_ERROR",
            message=message,
            details=details
        )

class ServiceUnavailableError(TranscriboError):
    """Raised when a required service is unavailable"""
    def __init__(
        self,
        service: str,
        message: Optional[str] = None,
        retry_after: Optional[int] = None
    ):
        details = {"service": service}
        if retry_after:
            details["retry_after"] = retry_after
            
        super().__init__(
            status_code=503,
            code="SERVICE_UNAVAILABLE",
            message=message or f"Service unavailable: {service}",
            details=details
        )
