"""Circuit breaker pattern implementation."""

import asyncio
import functools
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Any, Optional, Dict, List
from .logging import log_info, log_error, log_warning
from .metrics import track_error
from .exceptions import ServiceUnavailableError
from ..types import ErrorContext

T = TypeVar('T')

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"         # Failing, requests immediately fail
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for external service calls."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 30,
        timeout: float = 10.0,
        excluded_exceptions: Optional[List[type]] = None
    ):
        """Initialize circuit breaker.
        
        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before trying again
            timeout: Timeout for operations in seconds
            excluded_exceptions: Exceptions that don't count as failures
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.timeout = timeout
        self.excluded_exceptions = excluded_exceptions or []
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.last_success_time = None
        
        # Metrics
        self.success_count = 0
        self.total_calls = 0
        self.open_count = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator for circuit breaker.
        
        Args:
            func: Function to wrap
            
        Returns:
            Wrapped function with circuit breaker
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            """Wrapper function."""
            async with self._lock:
                self.total_calls += 1
                
                # Check if circuit is open
                if self.state == CircuitState.OPEN:
                    # Check if recovery timeout has elapsed
                    if (datetime.utcnow() - self.last_failure_time) > timedelta(seconds=self.recovery_timeout):
                        # Move to half-open state
                        self.state = CircuitState.HALF_OPEN
                        log_info(f"Circuit {self.name} moved to half-open state")
                    else:
                        # Circuit still open, fail fast
                        raise ServiceUnavailableError(
                            f"Service {self.name} is unavailable (circuit open)",
                            details={
                                "circuit": self.name,
                                "state": self.state.value,
                                "failure_count": self.failure_count,
                                "last_failure": self.last_failure_time,
                                "recovery_timeout": self.recovery_timeout
                            }
                        )
            
            # Execute function with timeout
            try:
                # Set timeout for operation
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout
                )
                
                async with self._lock:
                    # Success, reset failure count
                    if self.state == CircuitState.HALF_OPEN:
                        # Move back to closed state
                        self.state = CircuitState.CLOSED
                        log_info(f"Circuit {self.name} moved to closed state")
                    
                    self.failure_count = 0
                    self.last_success_time = datetime.utcnow()
                    self.success_count += 1
                
                return result
                
            except Exception as e:
                # Check if exception is excluded
                if any(isinstance(e, exc) for exc in self.excluded_exceptions):
                    # Don't count as failure
                    raise
                
                async with self._lock:
                    # Count as failure
                    self.failure_count += 1
                    self.last_failure_time = datetime.utcnow()
                    
                    # Check if threshold reached
                    if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                        # Open circuit
                        self.state = CircuitState.OPEN
                        self.open_count += 1
                        log_warning(f"Circuit {self.name} opened after {self.failure_count} failures")
                
                # Re-raise with context
                if isinstance(e, asyncio.TimeoutError):
                    error_context: ErrorContext = {
                        "operation": func.__name__,
                        "timestamp": datetime.utcnow(),
                        "details": {
                            "circuit": self.name,
                            "state": self.state.value,
                            "failure_count": self.failure_count,
                            "timeout": self.timeout
                        }
                    }
                    raise ServiceUnavailableError(
                        f"Service {self.name} timed out after {self.timeout} seconds",
                        details=error_context
                    ) from e
                else:
                    error_context = {
                        "operation": func.__name__,
                        "timestamp": datetime.utcnow(),
                        "details": {
                            "circuit": self.name,
                            "state": self.state.value,
                            "failure_count": self.failure_count,
                            "error": str(e)
                        }
                    }
                    raise ServiceUnavailableError(
                        f"Service {self.name} failed: {str(e)}",
                        details=error_context
                    ) from e
        
        return wrapper
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status.
        
        Returns:
            Dictionary with circuit breaker status
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "open_count": self.open_count,
            "last_failure": self.last_failure_time,
            "last_success": self.last_success_time,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "timeout": self.timeout
        }

class CircuitBreakerRegistry:
    """Registry for circuit breakers."""
    
    def __init__(self):
        """Initialize registry."""
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def register(self, circuit_breaker: CircuitBreaker) -> None:
        """Register circuit breaker.
        
        Args:
            circuit_breaker: Circuit breaker to register
        """
        async with self._lock:
            self.circuit_breakers[circuit_breaker.name] = circuit_breaker
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name.
        
        Args:
            name: Circuit breaker name
            
        Returns:
            Circuit breaker if found, None otherwise
        """
        async with self._lock:
            return self.circuit_breakers.get(name)
    
    async def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers.
        
        Returns:
            Dictionary of circuit breaker statuses
        """
        async with self._lock:
            return {
                name: cb.get_status()
                for name, cb in self.circuit_breakers.items()
            }

# Global registry
circuit_breaker_registry = CircuitBreakerRegistry()

def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 30,
    timeout: float = 10.0,
    excluded_exceptions: Optional[List[type]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for circuit breaker.
    
    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before trying again
        timeout: Timeout for operations in seconds
        excluded_exceptions: Exceptions that don't count as failures
        
    Returns:
        Decorated function
    """
    # Create circuit breaker
    cb = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        timeout=timeout,
        excluded_exceptions=excluded_exceptions
    )
    
    # Register circuit breaker
    asyncio.create_task(circuit_breaker_registry.register(cb))
    
    # Return decorator
    return cb
