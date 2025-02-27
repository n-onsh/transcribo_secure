"""Decorators for error handling and request tracking."""

import functools
import asyncio
from typing import Callable, TypeVar, Any, Optional, List, Dict
from datetime import datetime
from fastapi import HTTPException, Request
from .exceptions import TranscriboError
from .error_handling import format_error_response
from .logging import log_error, log_warning
from .metrics import track_error
from ..types import ErrorCode, ErrorContext

T = TypeVar('T')

def handle_errors(
    operation: Optional[str] = None,
    error_types: Optional[List[type]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to handle errors in route handlers.
    
    Args:
        operation: Operation name for error context
        error_types: List of error types to handle specifically
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Decorator function.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            """Wrapper function."""
            # Get request object if present
            request = next(
                (arg for arg in args if isinstance(arg, Request)),
                None
            )
            
            # Get operation name
            op_name = operation or func.__name__
            
            try:
                return await func(*args, **kwargs)
                
            except HTTPException as e:
                # Convert FastAPI HTTPException to TranscriboError
                error_context: ErrorContext = {
                    "operation": op_name,
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "status_code": e.status_code,
                        "headers": e.headers
                    }
                }
                
                # Map status code to error code
                if e.status_code == 400:
                    code = ErrorCode.INVALID_REQUEST
                elif e.status_code == 401:
                    code = ErrorCode.UNAUTHORIZED
                elif e.status_code == 403:
                    code = ErrorCode.FORBIDDEN
                elif e.status_code == 404:
                    code = ErrorCode.NOT_FOUND
                elif e.status_code == 409:
                    code = ErrorCode.CONFLICT
                elif e.status_code == 422:
                    code = ErrorCode.UNPROCESSABLE_ENTITY
                else:
                    code = ErrorCode.INTERNAL_ERROR
                
                raise TranscriboError(
                    message=e.detail,
                    code=code,
                    details=error_context
                )
                
            except Exception as e:
                # Check if error type should be handled specifically
                if error_types and any(isinstance(e, t) for t in error_types):
                    # Re-raise as is
                    raise
                
                # Create error context
                error_context = {
                    "operation": op_name,
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "error": str(e),
                        "function": func.__name__,
                        "args": str(args),
                        "kwargs": str(kwargs)
                    }
                }
                
                # Track error
                track_error(
                    error_type=e.__class__.__name__,
                    status_code=500,
                    operation=op_name
                )
                
                # Log error
                log_error(
                    f"Error in {op_name}: {str(e)}",
                    error_context
                )
                
                # Re-raise as TranscriboError
                if not isinstance(e, TranscriboError):
                    raise TranscriboError(
                        message=str(e),
                        code=ErrorCode.INTERNAL_ERROR,
                        details=error_context
                    ) from e
                raise
        
        return wrapper
    
    return decorator

def retry(
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    max_delay: float = 30.0,
    retryable_exceptions: Optional[List[type]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry logic.
    
    Args:
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries in seconds
        backoff_factor: Factor to increase delay by after each retry
        jitter: Whether to add random jitter to delay
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: Exceptions to retry on
        
    Returns:
        Decorated function
    """
    import random
    
    # Default retryable exceptions
    if retryable_exceptions is None:
        retryable_exceptions = [
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError
        ]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Decorator function.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            """Wrapper function."""
            # Initialize retry state
            retry_count = 0
            last_exception = None
            
            # Try operation with retries
            while retry_count <= max_retries:
                try:
                    # Execute function
                    if retry_count > 0:
                        log_warning(
                            f"Retry {retry_count}/{max_retries} for {func.__name__}"
                        )
                    
                    return await func(*args, **kwargs)
                    
                except Exception as e:
                    # Check if exception is retryable
                    if not any(isinstance(e, exc) for exc in retryable_exceptions):
                        # Not retryable, re-raise
                        raise
                    
                    # Save exception
                    last_exception = e
                    
                    # Check if max retries reached
                    if retry_count >= max_retries:
                        log_warning(
                            f"Max retries ({max_retries}) reached for {func.__name__}"
                        )
                        break
                    
                    # Calculate delay
                    delay = min(
                        retry_delay * (backoff_factor ** retry_count),
                        max_delay
                    )
                    
                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    # Log retry
                    log_warning(
                        f"Retrying {func.__name__} in {delay:.2f}s after error: {str(e)}"
                    )
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
                    
                    # Increment retry count
                    retry_count += 1
            
            # Max retries reached, re-raise last exception
            if last_exception:
                raise TranscriboError(
                    message=f"Operation {func.__name__} failed after {max_retries} retries",
                    code=ErrorCode.SERVICE_UNAVAILABLE,
                    details={
                        "operation": func.__name__,
                        "retries": retry_count,
                        "max_retries": max_retries,
                        "last_error": str(last_exception)
                    }
                ) from last_exception
            
            # This should never happen
            raise RuntimeError("Unexpected state in retry logic")
        
        return wrapper
    
    return decorator

def fallback(
    fallback_func: Callable[..., T],
    exceptions: Optional[List[type]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for fallback mechanism.
    
    Args:
        fallback_func: Function to call if primary function fails
        exceptions: Exceptions to trigger fallback on
        
    Returns:
        Decorated function
    """
    # Default to all exceptions if none provided
    if exceptions is None:
        exceptions = [Exception]
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        """Decorator function.
        
        Args:
            func: Primary function to decorate
            
        Returns:
            Decorated function
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            """Wrapper function."""
            try:
                # Try primary function
                return await func(*args, **kwargs)
                
            except Exception as e:
                # Check if exception should trigger fallback
                if not any(isinstance(e, exc) for exc in exceptions):
                    # Not fallback exception, re-raise
                    raise
                
                # Log fallback
                log_warning(
                    f"Falling back for {func.__name__} after error: {str(e)}"
                )
                
                # Call fallback function
                return await fallback_func(*args, **kwargs)
        
        return wrapper
    
    return decorator
