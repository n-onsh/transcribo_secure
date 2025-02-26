"""Route utilities for common route handler patterns."""

import functools
from typing import Type, TypeVar, Any, Dict, Optional
from pydantic import BaseModel
from ..utils.logging import log_error
from ..utils.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    TranscriboError
)
from ..utils.metrics import track_time, DB_OPERATION_DURATION

T = TypeVar('T', bound=BaseModel)

def map_to_response(
    model: Any,
    response_class: Type[T],
    **extra_fields
) -> T:
    """Map a model to a response class.
    
    Args:
        model: The model to map from (can be a dict or any object with dict() method)
        response_class: The response class to map to
        **extra_fields: Additional fields to include in the response
        
    Returns:
        An instance of the response class
    """
    # Convert model to dict if needed
    model_dict = model.dict() if hasattr(model, 'dict') else model
    
    # Filter fields to only include those in the response class
    response_fields = response_class.__annotations__.keys()
    filtered_dict = {
        k: v for k, v in model_dict.items()
        if k in response_fields
    }
    
    # Add extra fields
    filtered_dict.update(extra_fields)
    
    # Create response instance
    return response_class(**filtered_dict)

def handle_exceptions(operation: Optional[str] = None):
    """Decorator to handle exceptions in route handlers.
    
    Args:
        operation: Name of the operation for logging purposes
        
    Returns:
        Decorated function that handles exceptions consistently
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
                
            except (ResourceNotFoundError, ValidationError, TranscriboError):
                # Let error middleware handle these
                raise
                
            except Exception as e:
                log_error(f"Error in {operation or func.__name__}: {str(e)}")
                raise TranscriboError(
                    f"Failed to {operation or func.__name__}",
                    details={
                        "error": str(e),
                        "operation": operation or func.__name__
                    }
                )
                
        return wrapper
    return decorator

def track_operation(operation: str):
    """Decorator to track operation timing.
    
    Args:
        operation: Name of the operation to track
        
    Returns:
        Decorated function that tracks timing
    """
    def decorator(func):
        @functools.wraps(func)
        @track_time(DB_OPERATION_DURATION, {"operation": operation})
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

def route_handler(operation: str):
    """Combined decorator for common route handler patterns.
    
    This decorator combines:
    - Exception handling
    - Operation timing tracking
    - Standard response mapping
    
    Args:
        operation: Name of the operation
        
    Returns:
        Decorated function with standard route handler patterns
    """
    def decorator(func):
        @functools.wraps(func)
        @handle_exceptions(operation)
        @track_operation(operation)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
