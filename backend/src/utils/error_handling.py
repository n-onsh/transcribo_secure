"""Error handling utilities."""

from typing import Dict, Any, Optional, Type
from datetime import datetime
from fastapi import Request, status
from fastapi.responses import JSONResponse

from ..models.api import ApiErrorResponse
from ..utils.logging import log_error
from ..constants import ERROR_CODES
from ..types import ErrorContext
from ..utils.exceptions import (
    TranscriboError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    FileError,
    HashVerificationError,
    KeyVaultError,
    KeyManagementError,
    EncryptionError
)

def create_error_response(
    request: Request,
    error: str,
    code: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response.
    
    Args:
        request: FastAPI request
        error: Error message
        code: Error code
        status_code: HTTP status code
        details: Optional error details
        
    Returns:
        JSON response with error details
    """
    response = ApiErrorResponse(
        error=error,
        code=code,
        details=details,
        request_id=getattr(request.state, "request_id", None),
        timestamp=datetime.utcnow()
    )
    
    return JSONResponse(
        status_code=status_code,
        content=response.dict(exclude_none=True)
    )

ERROR_HANDLERS = {
    TranscriboError: (ERROR_CODES["INTERNAL_ERROR"], status.HTTP_500_INTERNAL_SERVER_ERROR),
    ValidationError: (ERROR_CODES["VALIDATION_ERROR"], status.HTTP_400_BAD_REQUEST),
    AuthenticationError: (ERROR_CODES["AUTHENTICATION_ERROR"], status.HTTP_401_UNAUTHORIZED),
    AuthorizationError: (ERROR_CODES["AUTHORIZATION_ERROR"], status.HTTP_403_FORBIDDEN),
    ResourceNotFoundError: (ERROR_CODES["NOT_FOUND_ERROR"], status.HTTP_404_NOT_FOUND),
    FileError: (ERROR_CODES["VALIDATION_ERROR"], status.HTTP_400_BAD_REQUEST),
    HashVerificationError: (ERROR_CODES["VALIDATION_ERROR"], status.HTTP_400_BAD_REQUEST),
    KeyVaultError: (ERROR_CODES["INTERNAL_ERROR"], status.HTTP_500_INTERNAL_SERVER_ERROR),
    KeyManagementError: (ERROR_CODES["INTERNAL_ERROR"], status.HTTP_500_INTERNAL_SERVER_ERROR),
    EncryptionError: (ERROR_CODES["INTERNAL_ERROR"], status.HTTP_500_INTERNAL_SERVER_ERROR)
}

def handle_error(
    request: Request,
    exc: Exception,
    error_context: Optional[ErrorContext] = None
) -> JSONResponse:
    """Handle exception and create error response.
    
    Args:
        request: FastAPI request
        exc: Exception to handle
        error_context: Optional error context
        
    Returns:
        JSON response with error details
    """
    # Get error handler config
    error_type = type(exc)
    error_code, status_code = ERROR_HANDLERS.get(
        error_type,
        (ERROR_CODES["INTERNAL_ERROR"], status.HTTP_500_INTERNAL_SERVER_ERROR)
    )
    
    # Get error details
    if hasattr(exc, "details"):
        details = getattr(exc, "details")
    else:
        details = error_context or {}
        
    # Add common fields
    if "timestamp" not in details:
        details["timestamp"] = datetime.utcnow()
    if "operation" not in details:
        details["operation"] = request.url.path
        
    # Add request details
    details["request"] = {
        "method": request.method,
        "url": str(request.url),
        "client": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent")
    }
    
    # Log error
    log_error(
        f"{error_type.__name__}: {str(exc)}",
        details
    )
    
    # Create response
    return create_error_response(
        request=request,
        error=str(exc),
        code=error_code,
        status_code=status_code,
        details=details
    )
