from fastapi import Request, HTTPException
from typing import Dict, Optional, List
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
import os
from ..utils.token_validation import TokenValidator

logger = logs.get_logger(__name__)

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
            logger.emit(
                "Failed to initialize token validator",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise
        
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
        
        logger.emit(
            "Auth middleware initialized",
            severity=Severity.INFO,
            attributes={
                "public_paths": list(self.public_paths),
                "role_mappings": self.role_mappings
            }
        )

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
            
            # Call next middleware/route handler
            response = await call_next(request)
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            # Get request details before potential attribute errors
            path = str(request.url.path) if request.url else "unknown"
            headers = dict(request.headers) if request.headers else {}
            method = request.method if hasattr(request, "method") else "unknown"
            client = request.client.host if request.client else "unknown"
            
            logger.emit(
                "Auth middleware error",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "path": path,
                    "request_id": headers.get("X-Request-ID"),
                    "method": method,
                    "client_host": client
                }
            )
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
