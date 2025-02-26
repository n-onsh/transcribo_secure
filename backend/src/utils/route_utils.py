"""Route utilities for common route handler patterns."""

import functools
from typing import (
    Type, TypeVar, Any, Dict, Optional, Callable, Awaitable,
    cast, Union, get_type_hints
)
from datetime import datetime
from pydantic import BaseModel, ValidationError as PydanticValidationError
from fastapi import Response
from ..utils.logging import log_error, log_info
from ..utils.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    TranscriboError,
    RouteError
)
from ..types import (
    ErrorContext,
    Result,
    RouteHandler,
    AsyncHandler
)
from ..utils.metrics import track_time, DB_OPERATION_DURATION

T = TypeVar('T', bound=BaseModel)
ResponseType = TypeVar('ResponseType', bound=BaseModel)
HandlerType = TypeVar('HandlerType', bound=RouteHandler)

def map_to_response(
    model: Any,
    response_class: Type[ResponseType],
    **extra_fields: Any
) -> ResponseType:
    """Map a model to a response class.
    
    Args:
        model: The model to map from (can be a dict or any object with dict() method)
        response_class: The response class to map to
        **extra_fields: Additional fields to include in the response
        
    Returns:
        An instance of the response class
        
    Raises:
        ValidationError: If mapping fails or validation fails
    """
    try:
        # Convert model to dict if needed
        model_dict = model.dict() if hasattr(model, 'dict') else model
        
        # Get response class fields
        response_fields = get_type_hints(response_class)
        
        # Filter fields to only include those in the response class
        filtered_dict = {
            k: v for k, v in model_dict.items()
            if k in response_fields
        }
        
        # Add extra fields
        filtered_dict.update(extra_fields)
        
        # Create and validate response instance
        try:
            response = response_class(**filtered_dict)
            response.validate()
            return response
        except PydanticValidationError as e:
            error_context: ErrorContext = {
                "operation": "validate_response",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": str(model),
                    "response_class": response_class.__name__
                }
            }
            raise ValidationError("Response validation failed", details=error_context)
            
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "map_to_response",
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "model": str(model),
                "response_class": response_class.__name__
            }
        }
        raise ValidationError("Failed to map response", details=error_context)

def handle_exceptions(operation: Optional[str] = None) -> Callable[[HandlerType], HandlerType]:
    """Decorator to handle exceptions in route handlers.
    
    Args:
        operation: Name of the operation for logging purposes
        
    Returns:
        Decorated function that handles exceptions consistently
        
    Example:
        @handle_exceptions("create_user")
        async def create_user(user_data: UserCreate) -> UserResponse:
            ...
    """
    def decorator(func: HandlerType) -> HandlerType:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
                
            except (ResourceNotFoundError, ValidationError, TranscriboError):
                # Let error middleware handle these
                raise
                
            except Exception as e:
                error_context: ErrorContext = {
                    "operation": operation or func.__name__,
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "error": str(e),
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                }
                log_error(f"Error in {operation or func.__name__}: {str(e)}")
                raise RouteError(
                    f"Failed to {operation or func.__name__}",
                    details=error_context
                )
                
        return cast(HandlerType, wrapper)
    return decorator

def track_operation(operation: str) -> Callable[[HandlerType], HandlerType]:
    """Decorator to track operation timing.
    
    Args:
        operation: Name of the operation to track
        
    Returns:
        Decorated function that tracks timing
        
    Example:
        @track_operation("create_user")
        async def create_user(user_data: UserCreate) -> UserResponse:
            ...
    """
    def decorator(func: HandlerType) -> HandlerType:
        @functools.wraps(func)
        @track_time(DB_OPERATION_DURATION, {"operation": operation})
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)
        return cast(HandlerType, wrapper)
    return decorator

def validate_response(
    response_class: Type[ResponseType]
) -> Callable[[HandlerType], HandlerType]:
    """Decorator to validate route handler responses.
    
    Args:
        response_class: Expected response class
        
    Returns:
        Decorated function that validates responses
        
    Example:
        @validate_response(UserResponse)
        async def get_user(user_id: str) -> UserResponse:
            ...
    """
    def decorator(func: HandlerType) -> HandlerType:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)
            
            # Skip validation for Response objects (e.g. FileResponse)
            if isinstance(result, Response):
                return result
                
            try:
                # Handle both single objects and lists
                if isinstance(result, list):
                    return [
                        map_to_response(item, response_class)
                        if not isinstance(item, response_class)
                        else item
                        for item in result
                    ]
                else:
                    return (
                        map_to_response(result, response_class)
                        if not isinstance(result, response_class)
                        else result
                    )
            except Exception as e:
                error_context: ErrorContext = {
                    "operation": "validate_response",
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "error": str(e),
                        "response_class": response_class.__name__,
                        "result": str(result)
                    }
                }
                raise ValidationError(
                    "Response validation failed",
                    details=error_context
                )
                
        return cast(HandlerType, wrapper)
    return decorator

def route_handler(
    operation: str,
    response_class: Optional[Type[ResponseType]] = None
) -> Callable[[HandlerType], HandlerType]:
    """Combined decorator for common route handler patterns.
    
    This decorator combines:
    - Exception handling
    - Operation timing tracking
    - Response validation (if response_class provided)
    
    Args:
        operation: Name of the operation
        response_class: Optional response class for validation
        
    Returns:
        Decorated function with standard route handler patterns
        
    Example:
        @route_handler("create_user", UserResponse)
        async def create_user(user_data: UserCreate) -> UserResponse:
            ...
    """
    def decorator(func: HandlerType) -> HandlerType:
        # Apply decorators in reverse order (inside out)
        decorated = func
        
        # Add response validation if response class provided
        if response_class is not None:
            decorated = validate_response(response_class)(decorated)
            
        # Add operation tracking
        decorated = track_operation(operation)(decorated)
        
        # Add exception handling
        decorated = handle_exceptions(operation)(decorated)
        
        return cast(HandlerType, decorated)
    return decorator
