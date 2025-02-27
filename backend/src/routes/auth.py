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

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: Optional[str] = None

class ExchangeTokenRequest(BaseModel):
    """Token exchange request model."""
    azure_token: str

class RefreshTokenRequest(BaseModel):
    """Token refresh request model."""
    refresh_token: str

class SessionInfo(BaseModel):
    """Session info response model."""
    id: str
    created_at: str
    last_used_at: str
    expires_at: str
    user_agent: Optional[str]
    ip_address: Optional[str]

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@router.post("/exchange-token", response_model=TokenResponse)
async def exchange_token(request: Request, token_request: ExchangeTokenRequest):
    """Exchange Azure AD token for session token.
    
    Args:
        request: FastAPI request
        token_request: Token exchange request
        
    Returns:
        Session token response
        
    Raises:
        HTTPException: If exchange fails
    """
    try:
        # Track operation
        track_auth_operation('exchange_token')

        user_service = service_provider.get(UserService)
        if not user_service:
            raise ConfigurationError("User service unavailable")
            
        # Validate Azure token
        azure_token = token_request.azure_token
        user = await user_service.validate_token(azure_token)
        if not user:
            raise AuthenticationError("Invalid Azure token")
            
        # Create session token
        token = await user_service.create_access_token(
            user=user,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
        )
        return TokenResponse(**token)
        
    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Token exchange failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Token exchange error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Token exchange failed"
        )

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: Request, refresh_request: RefreshTokenRequest):
    """Refresh access token.
    
    Args:
        request: FastAPI request
        refresh_request: Token refresh request
        
    Returns:
        New token response
        
    Raises:
        HTTPException: If refresh fails
    """
    try:
        # Track operation
        track_auth_operation('refresh_token')

        user_service = service_provider.get(UserService)
        if not user_service:
            raise ConfigurationError("User service unavailable")
            
        # Refresh token
        token = await user_service.refresh_token(
            refresh_token=refresh_request.refresh_token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None
        )
        if not token:
            raise AuthenticationError("Invalid refresh token")
            
        return TokenResponse(**token)
        
    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Token refresh failed: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Token refresh failed"
        )

@router.post("/logout")
async def logout(request: Request):
    """Logout and invalidate session.
    
    Args:
        request: FastAPI request
        
    Returns:
        Success response
    """
    try:
        # Track operation
        track_auth_operation('logout')

        user_service = service_provider.get(UserService)
        if not user_service:
            raise ConfigurationError("User service unavailable")
            
        # Get token from header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {"success": True}  # No token to invalidate
            
        token = auth_header.split(" ")[1]
        
        # Invalidate session
        await user_service.invalidate_session(token)
        return {"success": True}
        
    except Exception as e:
        log_error(f"Logout error: {str(e)}")
        return {"success": True}  # Always return success for logout

@router.get("/sessions", response_model=List[SessionInfo])
async def get_sessions(request: Request):
    """Get active sessions for current user.
    
    Args:
        request: FastAPI request
        
    Returns:
        List of active sessions
        
    Raises:
        HTTPException: If session retrieval fails
    """
    try:
        # Track operation
        track_auth_operation('get_sessions')

        auth_context = request.state.auth
        if not auth_context:
            raise AuthenticationError("Authentication required")
            
        user_service = service_provider.get(UserService)
        if not user_service:
            raise ConfigurationError("User service unavailable")
            
        # Get sessions
        sessions = await user_service.get_active_sessions(auth_context["user"]["id"])
        return [SessionInfo(**session) for session in sessions]
        
    except AuthenticationError as e:
        track_auth_error()
        log_error(f"Failed to get sessions: {str(e)}")
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        track_auth_error()
        log_error(f"Error getting sessions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get sessions"
        )

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
