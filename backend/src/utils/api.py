"""API utilities."""

from typing import List, Optional
from fastapi import APIRouter
from ..constants import API_V1_PREFIX

def create_api_router(
    prefix: str,
    tags: List[str],
    version_prefix: Optional[str] = API_V1_PREFIX
) -> APIRouter:
    """Create standardized API router.
    
    Args:
        prefix: Route prefix
        tags: OpenAPI tags
        version_prefix: API version prefix (default: /api/v1)
        
    Returns:
        Configured API router
    """
    # Skip version prefix for auth routes
    if prefix.startswith("/auth"):
        full_prefix = prefix
    else:
        full_prefix = f"{version_prefix}{prefix}"
        
    return APIRouter(
        prefix=full_prefix,
        tags=tags
    )

def get_error_code(status_code: int) -> str:
    """Get error code for status code.
    
    Args:
        status_code: HTTP status code
        
    Returns:
        Error code string
    """
    return f"ERR_{status_code}"
