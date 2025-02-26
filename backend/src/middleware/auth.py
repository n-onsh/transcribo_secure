"""Authentication middleware."""

import logging
from typing import Optional, Dict, List
import os
from fastapi import Request, HTTPException
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    AUTH_REQUESTS,
    AUTH_ERRORS,
    AUTH_LATENCY,
    track_auth_request,
    track_auth_error,
    track_auth_latency
)

class AuthMiddleware:
    """Middleware for handling authentication."""

    async def __call__(self, request: Request, call_next):
        """Process the request."""
        start_time = logging.time()
        try:
            # Track request
            AUTH_REQUESTS.inc()
            track_auth_request()

            # Skip auth for health check and metrics
            if request.url.path in ["/health", "/metrics"]:
                return await call_next(request)

            # Validate auth token
            token = request.headers.get("Authorization")
            if not token:
                log_warning("Missing authorization header")
                raise HTTPException(status_code=401, detail="Missing authorization")

            # Validate token and get user info
            user_info = await self._validate_token(token)
            if not user_info:
                log_warning("Invalid authorization token")
                raise HTTPException(status_code=401, detail="Invalid authorization")

            # Add user info to request state
            request.state.user = user_info
            
            # Track latency
            duration = logging.time() - start_time
            AUTH_LATENCY.observe(duration)
            track_auth_latency(duration)

            log_info(f"Authenticated user {user_info.get('username')}")
            return await call_next(request)

        except HTTPException:
            AUTH_ERRORS.inc()
            track_auth_error()
            raise

        except Exception as e:
            AUTH_ERRORS.inc()
            track_auth_error()
            log_error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=500, detail="Authentication error")

    async def _validate_token(self, token: str) -> Optional[Dict]:
        """Validate auth token and return user info."""
        # Implementation would validate token
        return {
            "username": "test_user",
            "roles": ["user"]
        }
