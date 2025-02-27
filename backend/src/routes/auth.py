"""Authentication routes."""

from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, List, Optional
from pydantic import BaseModel
from ..middleware.auth import AuthMiddleware
from ..services.provider import service_provider
from ..services.user_service import UserService
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    AUTH_OPERATIONS,
    AUTH_ERRORS,
    track_auth_operation,
    track_auth_error
)
from ..utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError
)
from ..types import UserInfo as UserInfoType
from ..config import config

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

# Initialize auth middleware
auth = AuthMiddleware()

class UserInfo(BaseModel):
    """User info response model."""
    id: str
    email: Optional[str]
    name: str
    roles: List[str]
    scopes: List[str]
    type: str  # 'azure_ad' or 'jwt'

class LoginRequest(BaseModel):
    """Login request model for JWT auth."""
    username: str
    password: str

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@router.get("/validate", response_model=UserInfo)
async def validate_token(request: Request):
    """Validate token and return user info.
    
    Args:
        request: FastAPI request
        
    Returns:
        User info if token is valid
        
    Raises:
        HTTPException: If validation fails
    """
    try:
        # Track operation
        track_auth_operation('validate_token')

        # Auth middleware will validate token and add user to request
        auth_context = request.state.auth
        if not auth_context:
            raise AuthenticationError("Authentication required")
            
        user = auth_context["user"]
        return UserInfo(
            id=user["id"],
            email=user.get("email"),
            name=user.get("username") or user.get("name", ""),
            roles=user.get("roles", []),
            scopes=user.get("scopes", []),
            type=config.auth.mode
        )

    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Token validation failed"
        )

@router.get("/me", response_model=UserInfo)
async def get_current_user(request: Request):
    """Get current user info.
    
    Args:
        request: FastAPI request
        
    Returns:
        Current user info
        
    Raises:
        HTTPException: If user info retrieval fails
    """
    try:
        # Track operation
        track_auth_operation('get_user')

        auth_context = request.state.auth
        if not auth_context:
            raise AuthenticationError("Authentication required")
            
        user = auth_context["user"]
        return UserInfo(
            id=user["id"],
            email=user.get("email"),
            name=user.get("username") or user.get("name", ""),
            roles=user.get("roles", []),
            scopes=user.get("scopes", []),
            type=config.auth.mode
        )

    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Failed to get user info: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user info"
        )

@router.get("/roles")
async def get_user_roles(request: Request):
    """Get current user roles.
    
    Args:
        request: FastAPI request
        
    Returns:
        User roles list
        
    Raises:
        HTTPException: If role retrieval fails
    """
    try:
        # Track operation
        track_auth_operation('get_roles')

        auth_context = request.state.auth
        if not auth_context:
            raise AuthenticationError("Authentication required")
            
        user = auth_context["user"]
        return {"roles": user.get("roles", [])}

    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Failed to get user roles: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Error getting user roles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user roles"
        )

@router.get("/has-role/{role}")
async def check_role(role: str, request: Request):
    """Check if user has specific role.
    
    Args:
        role: Role to check
        request: FastAPI request
        
    Returns:
        True if user has role, False otherwise
        
    Raises:
        HTTPException: If role check fails
    """
    try:
        # Track operation
        track_auth_operation('check_role')

        auth_context = request.state.auth
        if not auth_context:
            raise AuthenticationError("Authentication required")
            
        user = auth_context["user"]
        has_role = role in user.get("roles", [])
        return {"has_role": has_role}

    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Failed to check role: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Error checking role: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to check role"
        )

# JWT auth endpoints (development only)
@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login endpoint for JWT auth (development only).
    
    Args:
        request: Login request
        
    Returns:
        JWT token response
        
    Raises:
        HTTPException: If login fails
    """
    if config.auth.mode != "jwt":
        raise HTTPException(
            status_code=404,
            detail="Endpoint not available in current auth mode"
        )
        
    try:
        # Track operation
        track_auth_operation('login')

        user_service = service_provider.get(UserService)
        if not user_service:
            raise ConfigurationError("User service unavailable")
            
        # Get user by username
        user = await user_service.get_user_by_identity(request.username)
        if not user:
            raise AuthenticationError("Invalid credentials")
            
        # In development, we accept any password
        if config.environment != "development":
            raise HTTPException(
                status_code=404,
                detail="Endpoint not available in current environment"
            )
            
        # Create access token
        token = await user_service.create_access_token(user)
        return TokenResponse(**token)
        
    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Login failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except ConfigurationError as e:
        track_auth_error()
        log_error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Login failed"
        )
