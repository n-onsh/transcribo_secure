"""Request ID middleware."""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from ..constants import REQUEST_ID_HEADER
from ..utils.logging import log_info

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID to each request."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response with request ID header
        """
        # Get request ID from header or generate new one
        request_id = request.headers.get(REQUEST_ID_HEADER)
        if not request_id:
            request_id = str(uuid.uuid4())
            
        # Add to request state for access in route handlers
        request.state.request_id = request_id
        
        # Log request
        log_info(
            "Request started",
            {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client": request.client.host if request.client else None
            }
        )
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers[REQUEST_ID_HEADER] = request_id
        
        # Log response
        log_info(
            "Request completed",
            {
                "request_id": request_id,
                "status_code": response.status_code
            }
        )
        
        return response
