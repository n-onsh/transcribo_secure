"""Base service class with common functionality."""

import asyncio
from typing import Dict, Any, Optional, TypeVar, Generic, Callable, Awaitable, cast
from ..utils.logging import log_info, log_error
from ..utils.exceptions import TranscriboError
from ..utils.metrics import track_time, SERVICE_OPERATION_DURATION
from ..types import (
    ServiceProtocol,
    ServiceConfig,
    AsyncHandler,
    ErrorContext,
    Result
)

T = TypeVar('T', bound='BaseService')

class BaseService(Generic[T], ServiceProtocol):
    """Base class for services with standard initialization/cleanup."""
    
    def __init__(self, settings: Optional[ServiceConfig] = None) -> None:
        """Initialize base service.
        
        Args:
            settings: Optional service configuration
        """
        self.settings: ServiceConfig = cast(ServiceConfig, settings or {})
        self.initialized: bool = False
        self._locks: Dict[str, asyncio.Lock] = {}  # Operation locks for concurrency control
        
    async def initialize(self) -> None:
        """Initialize the service.
        
        This method:
        1. Checks if already initialized
        2. Calls implementation-specific initialization
        3. Sets initialized flag
        4. Logs completion
        
        Raises:
            TranscriboError: If initialization fails
        """
        if self.initialized:
            return

        try:
            await self._initialize_impl()
            self.initialized = True
            log_info(f"{self.__class__.__name__} initialized")
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize",
                "resource_id": self.__class__.__name__,
                "timestamp": asyncio.get_event_loop().time(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize {self.__class__.__name__}: {str(e)}")
            raise TranscriboError(
                f"Failed to initialize {self.__class__.__name__}",
                details=error_context
            )
            
    async def cleanup(self) -> None:
        """Clean up the service.
        
        This method:
        1. Checks if initialized
        2. Calls implementation-specific cleanup
        3. Clears initialized flag
        4. Logs completion
        
        Raises:
            TranscriboError: If cleanup fails
        """
        if not self.initialized:
            return
            
        try:
            await self._cleanup_impl()
            self.initialized = False
            log_info(f"{self.__class__.__name__} cleaned up")
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup",
                "resource_id": self.__class__.__name__,
                "timestamp": asyncio.get_event_loop().time(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during {self.__class__.__name__} cleanup: {str(e)}")
            raise TranscriboError(
                f"Failed to clean up {self.__class__.__name__}",
                details=error_context
            )
            
    async def _initialize_impl(self) -> None:
        """Implementation-specific initialization.
        
        Override this method to provide service-specific initialization.
        """
        pass
        
    async def _cleanup_impl(self) -> None:
        """Implementation-specific cleanup.
        
        Override this method to provide service-specific cleanup.
        """
        pass
        
    def _check_initialized(self) -> None:
        """Check if service is initialized.
        
        Raises:
            TranscriboError: If service is not initialized
        """
        if not self.initialized:
            raise TranscriboError(f"{self.__class__.__name__} not initialized")
            
    async def _with_lock(self, key: str, operation: AsyncHandler) -> Any:
        """Execute operation with a lock.
        
        Args:
            key: Lock key
            operation: Async operation to execute
            
        Returns:
            Result of the operation
            
        This method ensures only one operation with the same key
        can execute at a time.
        """
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
            
        async with self._locks[key]:
            return await operation()
            
    @track_time(SERVICE_OPERATION_DURATION)
    async def _execute_operation(
        self,
        operation: str,
        func: AsyncHandler,
        *args: Any,
        **kwargs: Any
    ) -> Result:
        """Execute a service operation with tracking.
        
        Args:
            operation: Operation name for tracking
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the operation
            
        This method:
        1. Checks if service is initialized
        2. Tracks operation timing
        3. Handles exceptions consistently
        """
        self._check_initialized()
        
        try:
            result = await func(*args, **kwargs)
            return {
                "success": True,
                "message": f"{operation} completed successfully",
                "data": result,
                "error": None
            }
            
        except TranscriboError:
            raise
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": operation,
                "resource_id": self.__class__.__name__,
                "timestamp": asyncio.get_event_loop().time(),
                "details": {
                    "error": str(e),
                    "args": args,
                    "kwargs": kwargs
                }
            }
            log_error(f"Error in {operation}: {str(e)}")
            raise TranscriboError(
                f"Failed to {operation}",
                details=error_context
            )
