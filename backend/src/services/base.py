"""Base service class."""

from typing import List, Type, TypeVar, Optional, Dict, Any, Set
from datetime import datetime
from ..types import ServiceConfig, ErrorContext
from ..utils.exceptions import ServiceError

T = TypeVar('T')

class BaseService:
    """Base class for all services."""
    
    # Class-level dependency declarations
    __dependencies__: List[Type['BaseService']] = []
    
    def __init__(self, config: Optional[ServiceConfig] = None):
        """Initialize service.
        
        Args:
            config: Optional service configuration
        """
        self.config = config or {}
        
        # Instance-level dependency tracking
        self._initialized = False
        self._dependencies: Set[Type['BaseService']] = set()
        
        # Add class-level dependencies
        if hasattr(self.__class__, "__dependencies__"):
            deps = getattr(self.__class__, "__dependencies__")
            if isinstance(deps, list):
                self._dependencies.update(deps)
    
    def add_dependency(self, service_type: Type['BaseService']) -> None:
        """Add dependency.
        
        Args:
            service_type: Service type to depend on
        """
        self._dependencies.add(service_type)
    
    def get_dependencies(self) -> Set[Type['BaseService']]:
        """Get service dependencies.
        
        Returns:
            Set of service types this service depends on
        """
        return self._dependencies
    
    def has_dependency(self, service_type: Type['BaseService']) -> bool:
        """Check if service has dependency.
        
        Args:
            service_type: Service type to check
            
        Returns:
            True if service depends on given type
        """
        return service_type in self._dependencies
    
    async def initialize(self) -> None:
        """Initialize service.
        
        This method should be overridden by services that need
        asynchronous initialization.
        """
        if self._initialized:
            return
            
        try:
            await self._initialize()
            self._initialized = True
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "service": self.__class__.__name__,
                    "error": str(e)
                }
            }
            raise ServiceError(
                f"Failed to initialize service {self.__class__.__name__}",
                details=error_context
            ) from e
    
    async def _initialize(self) -> None:
        """Internal initialization.
        
        This method should be overridden by services that need
        asynchronous initialization.
        """
        pass
    
    @property
    def initialized(self) -> bool:
        """Check if service is initialized.
        
        Returns:
            True if service is initialized
        """
        return self._initialized
    
    def __str__(self) -> str:
        """Get string representation.
        
        Returns:
            String representation of service
        """
        return f"{self.__class__.__name__}(initialized={self._initialized})"
    
    def __repr__(self) -> str:
        """Get detailed string representation.
        
        Returns:
            Detailed string representation of service
        """
        return (
            f"{self.__class__.__name__}("
            f"initialized={self._initialized}, "
            f"dependencies={[d.__name__ for d in self._dependencies]}"
            ")"
        )
