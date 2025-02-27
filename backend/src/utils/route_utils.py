"""Route utilities."""

from typing import TypeVar, Generic, Type, List, Dict, Any, Optional, Callable
from functools import wraps
from datetime import datetime
from fastapi import Request
from pydantic import BaseModel

from ..models.api import (
    ApiResponse,
    ApiListResponse,
    ApiErrorResponse,
    PaginationMetadata,
    CursorParams
)
from ..utils.api import get_error_code
from ..constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

T = TypeVar('T', bound=BaseModel)

def create_response(
    data: Any,
    response_model: Type[T],
    request: Request,
    meta: Dict[str, Any] = None
) -> ApiResponse[T]:
    """Create standard API response.
    
    Args:
        data: Response data
        response_model: Response model type
        request: FastAPI request
        meta: Optional metadata
        
    Returns:
        API response
    """
    return ApiResponse(
        data=map_to_response(data, response_model),
        meta=meta or {},
        request_id=getattr(request.state, "request_id", None),
        timestamp=datetime.utcnow()
    )

def create_list_response(
    data: List[Any],
    response_model: Type[T],
    request: Request,
    total: int,
    limit: int,
    next_cursor: Optional[str] = None,
    meta: Dict[str, Any] = None
) -> ApiListResponse[T]:
    """Create standard API list response.
    
    Args:
        data: List of response data
        response_model: Response model type
        request: FastAPI request
        total: Total number of items
        limit: Page size limit
        next_cursor: Optional next page cursor
        meta: Optional metadata
        
    Returns:
        API list response
    """
    return ApiListResponse(
        data=[map_to_response(item, response_model) for item in data],
        pagination=PaginationMetadata(
            total=total,
            limit=limit,
            has_more=next_cursor is not None,
            next_cursor=next_cursor
        ),
        meta=meta or {},
        request_id=getattr(request.state, "request_id", None),
        timestamp=datetime.utcnow()
    )

def create_error_response(
    request: Request,
    error: str,
    status_code: int,
    details: Dict[str, Any] = None
) -> ApiErrorResponse:
    """Create standard API error response.
    
    Args:
        request: FastAPI request
        error: Error message
        status_code: HTTP status code
        details: Optional error details
        
    Returns:
        API error response
    """
    return ApiErrorResponse(
        error=error,
        code=get_error_code(status_code),
        details=details,
        request_id=getattr(request.state, "request_id", None),
        timestamp=datetime.utcnow()
    )

def map_to_response(data: Any, response_model: Type[T]) -> T:
    """Map data to response model.
    
    Args:
        data: Data to map
        response_model: Response model type
        
    Returns:
        Response model instance
    """
    if isinstance(data, dict):
        return response_model(**data)
    elif isinstance(data, response_model):
        return data
    elif hasattr(data, "to_dict"):
        return response_model(**data.to_dict())
    else:
        raise ValueError(f"Cannot map {type(data)} to {response_model}")

def validate_pagination_params(
    limit: Optional[int] = None,
    cursor: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_direction: Optional[str] = None
) -> CursorParams:
    """Validate and normalize pagination parameters.
    
    Args:
        limit: Page size limit
        cursor: Pagination cursor
        sort_field: Sort field name
        sort_direction: Sort direction
        
    Returns:
        Normalized cursor parameters
        
    Raises:
        ValueError: If parameters are invalid
    """
    # Validate limit
    if limit is None:
        limit = DEFAULT_PAGE_SIZE
    elif limit <= 0:
        raise ValueError("Limit must be positive")
    elif limit > MAX_PAGE_SIZE:
        limit = MAX_PAGE_SIZE
        
    # Validate sort direction
    if sort_direction and sort_direction.lower() not in ["asc", "desc"]:
        raise ValueError("Sort direction must be 'asc' or 'desc'")
        
    return CursorParams(
        cursor=cursor,
        limit=limit,
        sort_field=sort_field or "created_at",
        sort_direction=sort_direction or "desc"
    )

def api_route_handler(operation_name: str, response_model: Type[T] = None):
    """Decorator for API route handlers.
    
    Args:
        operation_name: Operation name for logging/metrics
        response_model: Optional response model type
        
    Returns:
        Route handler decorator
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            for arg in kwargs.values():
                if isinstance(arg, Request):
                    request = arg
                    break
                    
            try:
                result = await func(*args, **kwargs)
                
                if response_model:
                    if isinstance(result, list):
                        # Get pagination params from kwargs
                        limit = kwargs.get("limit", DEFAULT_PAGE_SIZE)
                        cursor = kwargs.get("cursor")
                        total = len(result)  # This should come from service layer
                        
                        return create_list_response(
                            result,
                            response_model,
                            request,
                            total=total,
                            limit=limit,
                            next_cursor=cursor  # This should come from service layer
                        )
                    else:
                        return create_response(result, response_model, request)
                return result
                
            except Exception as e:
                # Let FastAPI exception handlers deal with it
                raise
                
        return wrapper
    return decorator
