"""Error handling middleware."""

import traceback
from datetime import datetime
from typing import Dict, Any, Optional, cast
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from ..utils.logging import log_error
from ..utils.exceptions import (
    TranscriboError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ConflictError,
    DependencyError,
    ServiceError,
    DatabaseError,
    StorageError,
    FileError,
    EditorError,
    RouteError,
    HashVerificationError,
    ZipError,
    TranscriptionError,
    EncryptionError,
    KeyManagementError,
    JobError
)
from ..types import ErrorContext
from ..utils.metrics import track_error

async def error_handler(request: Request, call_next) -> Response:
    """Handle errors in request processing.
    
    Args:
        request: FastAPI request
        call_next: Next middleware/handler in chain
        
    Returns:
        Response with error details if error occurred
    """
    try:
        return await call_next(request)

    except TranscriboError as e:
        # Get error context
        error_context = e.details or {}
        
        # Add common fields if not present
        if "timestamp" not in error_context:
            error_context["timestamp"] = datetime.utcnow()
        if "operation" not in error_context:
            error_context["operation"] = request.url.path
            
        # Add request details
        error_context["details"] = {
            **(error_context.get("details", {})),
            "method": request.method,
            "url": str(request.url),
            "client": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent")
        }
        
        # Track error metrics
        track_error(
            error_type=e.__class__.__name__,
            status_code=e.status_code,
            operation=error_context.get("operation", "unknown")
        )
        
        # Log error with context
        log_error(
            f"{e.__class__.__name__}: {e.message}",
            error_context
        )
        
        # Return error response
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": e.__class__.__name__,
                "message": e.message,
                "details": error_context.get("details", {})
            }
        )

    except Exception as e:
        # Create error context for unhandled exceptions
        error_context: ErrorContext = {
            "operation": request.url.path,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "traceback": traceback.format_exc(),
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent")
            }
        }
        
        # Track unhandled error
        track_error(
            error_type="UnhandledException",
            status_code=500,
            operation=error_context["operation"]
        )
        
        # Log unhandled error
        log_error(
            f"Unhandled exception: {str(e)}",
            error_context
        )
        
        # Return generic error response
        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred",
                "details": {
                    "request_id": request.state.request_id
                    if hasattr(request.state, "request_id")
                    else None
                }
            }
        )

def get_error_details(error: Exception) -> Dict[str, Any]:
    """Get error details for response.
    
    Args:
        error: Exception to get details for
        
    Returns:
        Dictionary of error details
    """
    if isinstance(error, TranscriboError):
        return {
            "error": error.__class__.__name__,
            "message": error.message,
            "details": error.details.get("details", {})
            if error.details
            else {}
        }
    else:
        return {
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "details": {}
        }

def get_error_response(
    error: Exception,
    status_code: Optional[int] = None
) -> JSONResponse:
    """Get error response.
    
    Args:
        error: Exception to create response for
        status_code: Optional status code override
        
    Returns:
        JSON response with error details
    """
    if isinstance(error, TranscriboError):
        return JSONResponse(
            status_code=status_code or error.status_code,
            content=get_error_details(error)
        )
    else:
        return JSONResponse(
            status_code=status_code or 500,
            content=get_error_details(error)
        )
