from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import time
from typing import Dict, Optional, Tuple
import re
from ..utils.metrics import (
    HTTP_REQUESTS_TOTAL,
    HTTP_ERROR_REQUESTS_TOTAL
)

class RateLimiter(BaseHTTPMiddleware):
    """Rate limiting middleware with per-route configuration"""
    def __init__(self, app):
        super().__init__(app)
        # Default limits
        self.default_rate = 100  # requests per minute
        self.default_burst = 50  # burst size
        
        # Per-route limits (path regex -> (rate, burst))
        self.route_limits = {
            r"/api/v1/files/.*": (20, 10),  # File operations
            r"/api/v1/transcriber/.*": (10, 5),  # Transcription operations
            r"/api/v1/jobs/.*": (50, 20),  # Job operations
            r"/api/v1/vocabulary/.*": (30, 15),  # Vocabulary operations
        }
        
        # Compile regexes
        self.route_patterns = {
            re.compile(pattern): limits
            for pattern, limits in self.route_limits.items()
        }
        
        # Request tracking
        self.requests: Dict[str, Dict[float, int]] = {}
        self.last_cleanup = time.time()

    def _get_route_limits(self, path: str) -> Tuple[int, int]:
        """Get rate limits for path"""
        for pattern, limits in self.route_patterns.items():
            if pattern.match(path):
                return limits
        return (self.default_rate, self.default_burst)

    def _get_client_id(self, request: Request) -> str:
        """Get unique client identifier"""
        # Use X-Forwarded-For if behind proxy, fallback to client host
        forwarded_for = request.headers.get("X-Forwarded-For")
        client_ip = forwarded_for.split(",")[0] if forwarded_for else request.client.host
        
        # Include path for per-route tracking
        return f"{client_ip}:{request.url.path}"

    def _is_rate_limited(self, client_id: str, rate: int, burst: int) -> Tuple[bool, Optional[int]]:
        """Check if request should be rate limited"""
        now = time.time()
        minute = int(now / 60)
        
        # Cleanup old entries every minute
        if now - self.last_cleanup > 60:
            self._cleanup()
            self.last_cleanup = now
        
        # Initialize tracking for new clients
        if client_id not in self.requests:
            self.requests[client_id] = {}
        
        # Get request count for current minute
        current_count = self.requests[client_id].get(minute, 0)
        
        # Check burst limit
        if current_count >= burst:
            # Calculate retry after
            seconds_in_minute = 60 - (now % 60)
            return True, int(seconds_in_minute)
        
        # Check rate limit
        total_count = sum(
            count for ts, count in self.requests[client_id].items()
            if ts >= minute - 1
        )
        
        if total_count >= rate:
            # Calculate retry after
            if minute - 1 in self.requests[client_id]:
                oldest_request = 60  # Wait for next minute
            else:
                oldest_request = 0
                for ts in self.requests[client_id]:
                    if ts < minute:
                        oldest_request = max(oldest_request, (ts + 1) * 60 - now)
            return True, int(oldest_request)
        
        # Update request count
        self.requests[client_id][minute] = current_count + 1
        return False, None

    def _cleanup(self):
        """Clean up old request tracking data"""
        now = time.time()
        minute = int(now / 60)
        
        for client_id in list(self.requests.keys()):
            # Remove entries older than 2 minutes
            self.requests[client_id] = {
                ts: count
                for ts, count in self.requests[client_id].items()
                if ts >= minute - 2
            }
            
            # Remove client if no recent requests
            if not self.requests[client_id]:
                del self.requests[client_id]

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Get route limits
        rate, burst = self._get_route_limits(request.url.path)
        
        # Check rate limit
        is_limited, retry_after = self._is_rate_limited(client_id, rate, burst)
        
        if is_limited:
            # Update metrics
            HTTP_ERROR_REQUESTS_TOTAL.labels(
                method=request.method,
                endpoint=request.url.path,
                error_type="rate_limit"
            ).inc()
            
            # Return 429 with retry information
            headers = {"Retry-After": str(retry_after)} if retry_after else {}
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "Too many requests",
                    "details": {
                        "retry_after": retry_after
                    } if retry_after else None
                },
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Update metrics
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()
        
        return response
