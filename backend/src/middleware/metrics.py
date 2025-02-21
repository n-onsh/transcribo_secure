from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ..utils.metrics import (
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_TOTAL,
    HTTP_ERROR_REQUESTS_TOTAL
)
import time
import re

class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting HTTP request metrics"""
    
    def __init__(self, app):
        super().__init__(app)
        # Compile regex for route parameter replacement
        self.param_pattern = re.compile(r'/[0-9a-fA-F-]+(?=/|$)')
    
    def normalize_path(self, path: str) -> str:
        """Normalize path by replacing route parameters with placeholders"""
        # Replace UUIDs and numeric IDs with {id}
        path = self.param_pattern.sub('/{id}', path)
        return path
    
    async def dispatch(self, request: Request, call_next):
        """Process request and record metrics"""
        start_time = time.time()
        
        # Get normalized path for metrics
        path = self.normalize_path(request.url.path)
        method = request.method
        
        try:
            response = await call_next(request)
            
            # Record request duration
            duration = time.time() - start_time
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code
            ).observe(duration)
            
            # Increment request counter
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status_code=response.status_code
            ).inc()
            
            return response
            
        except Exception as e:
            # Record error metrics
            duration = time.time() - start_time
            
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=path,
                status_code=500
            ).observe(duration)
            
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                status_code=500
            ).inc()
            
            HTTP_ERROR_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=path,
                error_type=e.__class__.__name__
            ).inc()
            
            raise
