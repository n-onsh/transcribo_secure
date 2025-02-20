from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import os
import asyncio
from .rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class AuthMiddleware:
    def __init__(self):
        """Initialize authentication middleware"""
        # Get configuration
        self.secret_key = os.getenv("JWT_SECRET_KEY")
        if not self.secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable not set")
            
        self.token_expiry = int(os.getenv("JWT_TOKEN_EXPIRY_HOURS", "24"))
        self.refresh_expiry = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRY_DAYS", "30"))
        self.key_rotation_days = int(os.getenv("JWT_KEY_ROTATION_DAYS", "30"))
        self.algorithm = "HS256"
        self.security = HTTPBearer()
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            window_size=60,  # 1 minute window
            max_requests=100  # 100 requests per minute
        )
        
        # Public paths that don't require authentication
        self.public_paths = {
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/refresh",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json"
        }
        
        # Initialize key rotation
        self.last_rotation = datetime.utcnow()
        self._key_rotation_task = None
        
        logger.info("Auth middleware initialized")

    async def __call__(self, request: Request):
        """Process request"""
        try:
            # Apply rate limiting
            # Apply rate limiting
            client_ip = request.client.host if request.client else "unknown"
            allowed, wait_time = self.rate_limiter.is_allowed(client_ip)
            
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Please wait {wait_time} seconds."
                )
            
            # Skip auth for public paths
            if request.url.path in self.public_paths:
                return True
            
            # Get token from header
            auth = await self.security(request)
            if not auth:
                raise HTTPException(
                    status_code=401,
                    detail="Missing authentication token"
                )
            
            # Verify token
            try:
                payload = jwt.decode(
                    auth.credentials,
                    self.secret_key,
                    algorithms=[self.algorithm]
                )
            except jwt.ExpiredSignatureError:
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired"
                )
            except jwt.InvalidTokenError:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token"
                )
            
            # Add user to request state
            request.state.user = {
                "id": payload["sub"],
                "email": payload.get("email"),
                "name": payload.get("name"),
                "roles": payload.get("roles", [])
            }
            
            return True
            
        except HTTPException as e:
            raise
        except Exception as e:
            logger.error(f"Auth middleware error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail="Internal server error"
            )

    def create_token(self, user_id: str, email: Optional[str] = None, name: Optional[str] = None, roles: Optional[list] = None) -> Tuple[str, str]:
        """Create JWT token"""
        try:
            # Create access token payload
            access_payload = {
                "sub": user_id,
                "exp": datetime.utcnow() + timedelta(hours=self.token_expiry),
                "type": "access"
            }
            
            if email:
                access_payload["email"] = email
            if name:
                access_payload["name"] = name
            if roles:
                access_payload["roles"] = roles
            
            # Create refresh token payload
            refresh_payload = {
                "sub": user_id,
                "exp": datetime.utcnow() + timedelta(days=self.refresh_expiry),
                "type": "refresh"
            }
            
            # Create tokens
            access_token = jwt.encode(
                access_payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            refresh_token = jwt.encode(
                refresh_payload,
                self.secret_key,
                algorithm=self.algorithm
            )
            
            return access_token, refresh_token
            
        except Exception as e:
            logger.error(f"Failed to create token: {str(e)}")
            raise

    def verify_token(self, token: str, token_type: str = "access") -> Dict:
        """Verify JWT token"""
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid token type. Expected {token_type}"
                )
            
            return {
                "id": payload["sub"],
                "email": payload.get("email"),
                "name": payload.get("name"),
                "roles": payload.get("roles", [])
            }
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )

    def refresh_token(self, refresh_token: str) -> Tuple[str, str]:
        """Refresh JWT tokens"""
        try:
            # Verify refresh token
            user = self.verify_token(refresh_token, "refresh")
            
            # Create new tokens
            return self.create_token(
                user["sub"],
                user.get("email"),
                user.get("name"),
                user.get("roles")
            )
        except Exception as e:
            logger.error(f"Failed to refresh token: {str(e)}")
            raise

    async def _rotate_key_periodically(self):
        """Periodically rotate the JWT secret key"""
        while True:
            try:
                # Sleep until next rotation
                days_since_rotation = (datetime.utcnow() - self.last_rotation).days
                if days_since_rotation >= self.key_rotation_days:
                    # Generate new key
                    new_key = os.urandom(32).hex()
                    
                    # Update environment variable
                    os.environ["JWT_SECRET_KEY"] = new_key
                    self.secret_key = new_key
                    
                    # Update last rotation time
                    self.last_rotation = datetime.utcnow()
                    
                    logger.info("Rotated JWT secret key")
                
                # Sleep for a day
                await asyncio.sleep(24 * 60 * 60)
                
            except Exception as e:
                logger.error(f"Failed to rotate JWT key: {str(e)}")
                await asyncio.sleep(60 * 60)  # Retry in an hour

    def require_roles(self, roles: list):
        """Decorator to require specific roles"""
        def decorator(func):
            async def wrapper(request: Request, *args, **kwargs):
                # Get user roles
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
        return role in request.state.user.get("roles", [])

    def is_admin(self, request: Request) -> bool:
        """Check if user is admin"""
        return self.has_role(request, "admin")

    def get_user(self, request: Request) -> Dict:
        """Get user from request"""
        return request.state.user
