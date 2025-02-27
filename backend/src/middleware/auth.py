"""Authentication middleware."""

from typing import Optional, Dict, Any, cast
from datetime import datetime
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
from ..types import (
    UserInfo,
    AuthContext,
    ErrorContext
)
from ..utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError
)
from ..services.provider import service_provider
from ..services.user_service import UserService
from ..utils.token_validation import TokenValidator
from ..config import config

class AuthMiddleware:
    """Middleware for handling authentication."""

    def __init__(self):
        """Initialize auth middleware."""
        self.user_service: Optional[UserService] = None
        self.token_validator: Optional[TokenValidator] = None

    async def initialize(self) -> None:
        """Initialize middleware."""
        try:
            # Initialize services
            self.user_service = service_provider.get(UserService)
            if not self.user_service:
                error_context: ErrorContext = {
                    "operation": "initialize_auth",
                    "timestamp": datetime.utcnow(),
                    "details": {"error": "User service unavailable"}
                }
                raise ConfigurationError(
                    "User service unavailable",
                    details=error_context
                )
            await self.user_service.initialize()
            
            # Initialize token validator for Azure AD token exchange
            self.token_validator = TokenValidator()
            
            log_info("Auth middleware initialized")

        except Exception as e:
            error_context = {
                "operation": "initialize_auth",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize auth middleware: {str(e)}")
            raise ConfigurationError(
                "Failed to initialize auth middleware",
                details=error_context
            )

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public (no auth required).
        
        Args:
            path: Request path
            
        Returns:
            True if public endpoint, False otherwise
        """
        public_paths = [
            "/health",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/exchange-token",  # Allow token exchange without auth
            "/auth/refresh"  # Allow token refresh without auth
        ]
        
        for public_path in public_paths:
            if path.startswith(public_path):
                return True
                
        return False

    def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from request.
        
        Args:
            request: FastAPI request
            
        Returns:
            Token if found, None otherwise
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None
            
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
            
        return parts[1]

    async def _validate_token(self, token: str, request: Request) -> Optional[Dict[str, Any]]:
        """Validate token and get user info.
        
        Args:
            token: Access token string
            request: FastAPI request
            
        Returns:
            User info if token is valid, None otherwise
            
        Raises:
            AuthenticationError: If validation fails
        """
        if not self.user_service:
            log_error("User service not initialized")
            return None
            
        try:
            # Validate token and get user
            user = await self.user_service.validate_token(token)
            if not user:
                return None
                
            return user.to_dict()
            
        except AuthenticationError as e:
            log_error(f"Token validation error: {str(e)}")
            raise
        except Exception as e:
            log_error(f"Token validation error: {str(e)}")
            return None

    def _create_auth_context(self, user: Dict[str, Any], request: Request) -> AuthContext:
        """Create authentication context.
        
        Args:
            user: User information
            request: FastAPI request
            
        Returns:
            Authentication context
        """
        return {
            "user": user,
            "token": {
                "sub": user.get("id"),
                "exp": datetime.utcnow(),  # Will be set by token validation
                "scope": user.get("scopes", []),
                "roles": user.get("roles", []),
                "preferred_username": user.get("username") or user.get("name"),
                "email": user.get("email")
            },
            "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
            "timestamp": datetime.utcnow(),
            "user_agent": request.headers.get("user-agent"),
            "ip_address": request.client.host if request.client else None
        }

    async def __call__(self, request: Request, call_next):
        """Process the request.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response from next handler
            
        Raises:
            HTTPException: If authentication fails
        """
        start_time = datetime.utcnow()
        try:
            # Track request
            AUTH_REQUESTS.inc()
            track_auth_request()

            # Skip auth for public endpoints
            if self._is_public_endpoint(request.url.path):
                return await call_next(request)

            # Get and validate auth token
            token = self._extract_token(request)
            if not token:
                raise AuthenticationError("Missing authorization token")

            # Validate token and get user info
            user = await self._validate_token(token, request)
            if not user:
                raise AuthenticationError("Invalid authorization token")

            # Create auth context
            auth_context = self._create_auth_context(user, request)

            # Add auth context to request state
            request.state.auth = auth_context
            
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            AUTH_LATENCY.observe(duration)
            track_auth_latency(duration)

            log_info(f"Authenticated user {user.get('username') or user.get('name')}")
            return await call_next(request)

        except AuthenticationError as e:
            AUTH_ERRORS.inc()
            track_auth_error()
            log_error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=401, detail=str(e))
        except AuthorizationError as e:
            AUTH_ERRORS.inc()
            track_auth_error()
            log_error(f"Authorization error: {str(e)}")
            raise HTTPException(status_code=403, detail=str(e))
        except Exception as e:
            AUTH_ERRORS.inc()
            track_auth_error()
            log_error(f"Authentication error: {str(e)}")
            raise HTTPException(status_code=500, detail="Authentication error")
