from fastapi import Request, HTTPException
import logging
from typing import Dict, Optional, List
import os
from .rate_limiter import RateLimiter
from ..utils.token_validation import TokenValidator

logger = logging.getLogger(__name__)

class AuthMiddleware:
    def __init__(self):
        """Initialize authentication middleware"""
        # Get configuration
        self.encryption_key = os.getenv("ENCRYPTION_KEY")
        if not self.encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        
        # Initialize token validator
        try:
            self.token_validator = TokenValidator()
        except Exception as e:
            logger.error(f"Failed to initialize token validator: {str(e)}")
            raise
        
        # Initialize rate limiter with FastAPI app
        self.rate_limiter = None  # Will be set when used in FastAPI middleware
        
        # Public paths that don't require authentication
        self.public_paths = {
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        
        # Role mappings
        self.role_mappings = {
            "Admin": ["admin"],
            "User": ["user"],
            "Service": ["service"]
        }
        
        logger.info("Auth middleware initialized")

    def _map_azure_roles(self, azure_roles: List[str]) -> List[str]:
        """Map Azure AD roles to system roles"""
        system_roles = []
        for azure_role in azure_roles:
            if azure_role in self.role_mappings:
                system_roles.extend(self.role_mappings[azure_role])
        return list(set(system_roles))  # Remove duplicates

    async def __call__(self, request: Request, call_next):
        """Process request"""
        try:
            # Rate limiting is handled by the RateLimiter middleware
            
            path = request.url.path
            headers = request.headers
            
            # Initialize request state
            if not hasattr(request.state, "user"):
                request.state.user = None
            
            # Skip auth for public paths
            if path in self.public_paths:
                return await call_next(request)
            
            # Skip auth for metrics endpoint
            if path.rstrip('/') == '/metrics':
                return await call_next(request)
            
            # Check for service auth (encryption key)
            encryption_key = headers.get("X-Encryption-Key")
            if encryption_key and encryption_key == self.encryption_key:
                # Add service user to request state
                request.state.user = {
                    "id": "transcriber-service",
                    "roles": ["service"],
                    "type": "service"
                }
                return await call_next(request)
            
            # Check for Azure AD token
            auth_header = headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required"
                )
            
            # Extract and validate token
            token = auth_header.split(" ")[1]
            
            # Validate token
            token_data = self.token_validator.validate_token(token)
            
            # Get user info
            user_info = self.token_validator.get_user_info(token_data)
            
            # Map roles
            azure_roles = user_info.get("roles", [])
            system_roles = self._map_azure_roles(azure_roles)
            
            # Add user to request state
            request.state.user = {
                "id": user_info["id"],
                "email": user_info["email"],
                "name": user_info["name"],
                "roles": system_roles,
                "groups": user_info["groups"],
                "type": "user"
            }
            
            return await call_next(request)
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Auth middleware error: {str(e)}", 
                        extra={
                            "logger": "src.middleware.auth",
                            "path": request.url.path,
                            "line": 121,
                            "func": "__call__",
                            "request_id": request.headers.get("X-Request-ID"),
                            "method": request.method,
                            "client_host": request.client.host if request.client else None
                        })
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

    def require_roles(self, roles: List[str]):
        """Decorator to require specific roles"""
        def decorator(func):
            async def wrapper(request: Request, *args, **kwargs):
                # Get user roles
                if not request.state.user:
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication required"
                    )
                
                user_roles = request.state.user.get("roles", [])
                
                # Check if user has required role
                if not any(role in user_roles for role in roles):
                    raise HTTPException(
                        status_code=403,
                        detail="Insufficient permissions"
                    )
                
                return await func(request, *args, **kwargs)
            return wrapper
        return decorator

    def has_role(self, request: Request, role: str) -> bool:
        """Check if user has role"""
        if not request.state.user:
            return False
        return role in request.state.user.get("roles", [])

    def is_service(self, request: Request) -> bool:
        """Check if request is from a service"""
        return self.has_role(request, "service")

    def get_user(self, request: Request) -> Optional[Dict]:
        """Get user from request"""
        return request.state.user
