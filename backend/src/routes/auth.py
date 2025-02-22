from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, List
import logging
from ..middleware.auth import AuthMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

# Initialize auth middleware
auth = AuthMiddleware()

class UserInfo(BaseModel):
    """User info response model"""
    id: str
    email: str
    name: str
    roles: List[str]
    groups: List[str]
    type: str

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@router.get("/validate", response_model=UserInfo)
async def validate_token(request: Request):
    """Validate token and return user info"""
    try:
        # Auth middleware will validate token and add user to request
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Token validation failed"
        )

@router.get("/me", response_model=UserInfo)
async def get_current_user(request: Request):
    """Get current user info"""
    try:
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user info: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user info"
        )

@router.get("/roles")
async def get_user_roles(request: Request):
    """Get current user roles"""
    try:
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )
        return {"roles": user.get("roles", [])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user roles: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get user roles"
        )

@router.get("/has-role/{role}")
async def check_role(role: str, request: Request):
    """Check if user has specific role"""
    try:
        has_role = auth.has_role(request, role)
        return {"has_role": has_role}
    except Exception as e:
        logger.error(f"Role check failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Role check failed"
        )
