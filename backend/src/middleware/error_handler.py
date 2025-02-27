"""Error handling middleware."""

from typing import Dict, Any, Optional, Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from ..services.error_tracking import ErrorTrackingService
from ..types import (
    ErrorCode,
    ErrorSeverity,
    EnhancedErrorContext,
    ErrorResponse,
    RecoverySuggestion
)
from ..utils.logging import log_error
from ..utils.exceptions import TranscriboError

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling errors and providing enhanced error responses."""
    
    def __init__(
        self,
        app: Any,
        error_tracking_service: ErrorTrackingService,
        error_handlers: Optional[Dict[str, Callable]] = None
    ):
        """Initialize middleware.
        
        Args:
            app: FastAPI application
            error_tracking_service: Error tracking service instance
            error_handlers: Optional custom error handlers
        """
        super().__init__(app)
        self.error_tracking = error_tracking_service
        self.error_handlers = error_handlers or {}
        
        # Default error handlers
        self.default_handlers = {
            "ValidationError": self._handle_validation_error,
            "AuthenticationError": self._handle_auth_error,
            "AuthorizationError": self._handle_auth_error,
            "ResourceNotFoundError": self._handle_not_found_error,
            "StorageError": self._handle_storage_error,
            "TranscriptionError": self._handle_transcription_error,
            "DatabaseError": self._handle_database_error,
            "ZipError": self._handle_zip_error
        }
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        """Handle request and catch errors.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/endpoint
            
        Returns:
            Response
        """
        try:
            response = await call_next(request)
            return response
            
        except Exception as e:
            # Get error details
            error_type = type(e).__name__
            error_message = str(e)
            
            # Get error context
            error_context = await self._get_error_context(request, e)
            
            # Track error
            await self.error_tracking.track_error(error_context)
            
            # Log error
            log_error(
                f"{error_type}: {error_message}",
                error_context.details
            )
            
            # Get error handler
            handler = self.error_handlers.get(
                error_type,
                self.default_handlers.get(
                    error_type,
                    self._handle_unknown_error
                )
            )
            
            # Handle error
            return await handler(request, e, error_context)
    
    async def _get_error_context(
        self,
        request: Request,
        error: Exception
    ) -> EnhancedErrorContext:
        """Get enhanced error context.
        
        Args:
            request: FastAPI request
            error: Exception instance
            
        Returns:
            Enhanced error context
        """
        # Get basic error info
        error_type = type(error).__name__
        error_message = str(error)
        
        # Get request details
        operation = request.url.path
        request_id = getattr(request.state, "request_id", None)
        user_id = getattr(request.state, "user_id", None)
        
        # Get error details
        if isinstance(error, TranscriboError):
            details = error.details
            severity = error.severity
            is_retryable = error.is_retryable
            retry_after = error.retry_after
        else:
            details = {}
            severity = ErrorSeverity.ERROR
            is_retryable = False
            retry_after = None
        
        # Add request info to details
        details["request"] = {
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "client": request.client.host if request.client else None
        }
        
        # Get recovery suggestions
        recovery_suggestions = await self.error_tracking.get_recovery_suggestions(
            error_type,
            details
        )
        
        return EnhancedErrorContext(
            operation=operation,
            timestamp=request.state.start_time,
            severity=severity,
            resource_id=None,  # Set if applicable
            user_id=user_id,
            request_id=request_id,
            details=details,
            recovery_suggestions=recovery_suggestions,
            error_category=error_type,
            is_retryable=is_retryable,
            retry_after=retry_after
        )
    
    def _create_error_response(
        self,
        error: Exception,
        context: EnhancedErrorContext,
        status_code: int = 500
    ) -> JSONResponse:
        """Create error response.
        
        Args:
            error: Exception instance
            context: Error context
            status_code: HTTP status code
            
        Returns:
            JSON response
        """
        response = ErrorResponse(
            error=type(error).__name__,
            code=getattr(error, "code", ErrorCode.INTERNAL_ERROR),
            message=str(error),
            request_id=context.request_id,
            details=context.details,
            severity=context.severity,
            recovery_suggestions=context.recovery_suggestions,
            is_retryable=context.is_retryable,
            retry_after=context.retry_after
        )
        
        return JSONResponse(
            status_code=status_code,
            content=response.dict(exclude_none=True)
        )
    
    async def _handle_validation_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle validation errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        return self._create_error_response(error, context, 400)
    
    async def _handle_auth_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle authentication/authorization errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        status_code = 401 if "Authentication" in type(error).__name__ else 403
        return self._create_error_response(error, context, status_code)
    
    async def _handle_not_found_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle not found errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        return self._create_error_response(error, context, 404)
    
    async def _handle_storage_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle storage errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        # Add default recovery suggestions
        context.recovery_suggestions.extend([
            RecoverySuggestion(
                action="Check Storage",
                description="Verify storage service is accessible"
            ),
            RecoverySuggestion(
                action="Check Permissions",
                description="Verify you have the required permissions"
            )
        ])
        
        return self._create_error_response(error, context, 500)
    
    async def _handle_transcription_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle transcription errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        # Add default recovery suggestions
        context.recovery_suggestions.extend([
            RecoverySuggestion(
                action="Check Audio",
                description="Verify audio file is valid and not corrupted"
            ),
            RecoverySuggestion(
                action="Try Different Model",
                description="Try using a different transcription model"
            )
        ])
        
        return self._create_error_response(error, context, 500)
    
    async def _handle_database_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle database errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        # Add default recovery suggestions
        context.recovery_suggestions.extend([
            RecoverySuggestion(
                action="Try Again",
                description="The database may be temporarily unavailable"
            )
        ])
        
        return self._create_error_response(error, context, 500)
    
    async def _handle_zip_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle ZIP file errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        # Add default recovery suggestions
        context.recovery_suggestions.extend([
            RecoverySuggestion(
                action="Check ZIP File",
                description="Verify ZIP file is not corrupted"
            ),
            RecoverySuggestion(
                action="Check Contents",
                description="Verify ZIP contains supported file types"
            )
        ])
        
        return self._create_error_response(error, context, 400)
    
    async def _handle_unknown_error(
        self,
        request: Request,
        error: Exception,
        context: EnhancedErrorContext
    ) -> Response:
        """Handle unknown errors.
        
        Args:
            request: FastAPI request
            error: Exception instance
            context: Error context
            
        Returns:
            Error response
        """
        # Add default recovery suggestions
        context.recovery_suggestions.extend([
            RecoverySuggestion(
                action="Try Again",
                description="The error may be temporary"
            ),
            RecoverySuggestion(
                action="Contact Support",
                description="If the error persists, contact support"
            )
        ])
        
        return self._create_error_response(error, context, 500)
