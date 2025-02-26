"""Error handling middleware."""

import uuid
from typing import Callable, Dict, Any, Optional
from datetime import datetime
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from ..utils.logging import log_error
from ..utils.exceptions import (
    TranscriboError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ConflictError,
    RateLimitError,
    DatabaseError,
    StorageError,
    TranscriptionError,
    ConfigurationError
)
from ..types import ErrorContext
from ..models.base import ErrorResponse

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling errors."""
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Handle request and catch errors.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
            
        Returns:
            Response with error details if error occurred
        """
        try:
            return await call_next(request)
            
        except Exception as e:
            return await self.handle_error(e, request)
            
    async def handle_error(
        self,
        error: Exception,
        request: Request
    ) -> JSONResponse:
        """Handle different types of errors.
        
        Args:
            error: Exception that occurred
            request: FastAPI request
            
        Returns:
            JSON response with error details
        """
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        
        # Get basic error context
        error_context: ErrorContext = {
            "operation": request.url.path,
            "timestamp": datetime.utcnow(),
            "trace_id": request_id,
            "details": {
                "method": request.method,
                "url": str(request.url),
                "client_host": request.client.host if request.client else None,
                "headers": dict(request.headers)
            }
        }
        
        # Handle different error types
        if isinstance(error, PydanticValidationError):
            return self.handle_validation_error(error, error_context)
            
        elif isinstance(error, SQLAlchemyError):
            return self.handle_database_error(error, error_context)
            
        elif isinstance(error, TranscriboError):
            return self.handle_transcribo_error(error, error_context)
            
        else:
            return self.handle_unknown_error(error, error_context)
            
    def handle_validation_error(
        self,
        error: PydanticValidationError,
        context: ErrorContext
    ) -> JSONResponse:
        """Handle Pydantic validation errors.
        
        Args:
            error: Validation error
            context: Error context
            
        Returns:
            JSON response with validation error details
        """
        # Extract validation error details
        error_details = {
            "validation_errors": [
                {
                    "loc": err["loc"],
                    "msg": err["msg"],
                    "type": err["type"]
                }
                for err in error.errors()
            ]
        }
        context["details"].update(error_details)
        
        response = ErrorResponse(
            code="VALIDATION_ERROR",
            message="Invalid input data",
            details=context,
            help_url="https://docs.transcribo.io/errors/validation",
            request_id=context["trace_id"],
            timestamp=context["timestamp"]
        )
        
        return JSONResponse(
            status_code=400,
            content=response.model_dump()
        )
        
    def handle_database_error(
        self,
        error: SQLAlchemyError,
        context: ErrorContext
    ) -> JSONResponse:
        """Handle SQLAlchemy database errors.
        
        Args:
            error: Database error
            context: Error context
            
        Returns:
            JSON response with database error details
        """
        # Log the full error for debugging
        log_error(f"Database error: {str(error)}", exc_info=error)
        
        response = ErrorResponse(
            code="DATABASE_ERROR",
            message="Database operation failed",
            details=context,
            help_url="https://docs.transcribo.io/errors/database",
            request_id=context["trace_id"],
            timestamp=context["timestamp"]
        )
        
        return JSONResponse(
            status_code=500,
            content=response.model_dump()
        )
        
    def handle_transcribo_error(
        self,
        error: TranscriboError,
        context: ErrorContext
    ) -> JSONResponse:
        """Handle application-specific errors.
        
        Args:
            error: Application error
            context: Error context
            
        Returns:
            JSON response with error details
        """
        # Merge error details with context
        if error.details:
            context["details"].update(error.details.get("details", {}))
        
        response = ErrorResponse(
            code=error.__class__.__name__.upper(),
            message=str(error),
            details=context,
            help_url=error.help_url,
            request_id=context["trace_id"],
            timestamp=context["timestamp"]
        )
        
        return JSONResponse(
            status_code=error.status_code,
            content=response.model_dump()
        )
        
    def handle_unknown_error(
        self,
        error: Exception,
        context: ErrorContext
    ) -> JSONResponse:
        """Handle unknown errors.
        
        Args:
            error: Unknown error
            context: Error context
            
        Returns:
            JSON response with error details
        """
        # Log the full error for debugging
        log_error(f"Unexpected error: {str(error)}", exc_info=error)
        
        response = ErrorResponse(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred",
            details=context,
            help_url="https://docs.transcribo.io/errors/internal",
            request_id=context["trace_id"],
            timestamp=context["timestamp"]
        )
        
        return JSONResponse(
            status_code=500,
            content=response.model_dump()
        )
