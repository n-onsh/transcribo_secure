"""Service provider module."""

from typing import Dict, Any, Type, TypeVar, Optional, cast, Set
from enum import Enum
from datetime import datetime
from .base import BaseService
from ..config import config, ConfigurationService
from ..utils.exceptions import DependencyError
from ..utils.logging import log_warning
from ..types import ErrorContext

T = TypeVar('T', bound=BaseService)

class ServiceLifetime(str, Enum):
    """Service lifetime."""
    SINGLETON = "singleton"  # One instance for the application
    SCOPED = "scoped"       # One instance per request
    TRANSIENT = "transient" # New instance each time

class ServiceProvider:
    """Service provider."""
    
    _instance = None
    
    def __new__(cls):
        """Create singleton instance."""
        if cls._instance is None:
            cls._instance = super(ServiceProvider, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize service provider."""
        if self._initialized:
            return
            
        self._initialized = True
        self.services: Dict[Type[Any], Any] = {}
        self.config = config
        
        # Track dependencies for circular dependency detection
        self._dependencies: Dict[Type[Any], Set[Type[Any]]] = {}
    
    def register(self, service_type: Type[T], service: T) -> None:
        """Register service.
        
        Args:
            service_type: Service type
            service: Service instance
        """
        # Check for circular dependencies
        if hasattr(service, "__dependencies__"):
            deps = set(getattr(service, "__dependencies__"))
            self._dependencies[service_type] = deps
            
            # Check for circular dependencies
            visited = set()
            path = []
            
            def check_circular(svc_type: Type[Any]) -> bool:
                if svc_type in path:
                    # Found circular dependency
                    cycle = " -> ".join(t.__name__ for t in path[path.index(svc_type):] + [svc_type])
                    log_warning(
                        f"Circular dependency detected: {cycle}",
                        extra={
                            "service_type": service_type.__name__,
                            "dependencies": [d.__name__ for d in deps],
                            "cycle": cycle
                        }
                    )
                    return True
                    
                if svc_type in visited:
                    return False
                    
                visited.add(svc_type)
                path.append(svc_type)
                
                for dep in self._dependencies.get(svc_type, set()):
                    if check_circular(dep):
                        return True
                        
                path.pop()
                return False
            
            for dep in deps:
                if check_circular(dep):
                    break
        
        self.services[service_type] = service
    
    def get(self, service_type: Type[T]) -> Optional[T]:
        """Get service.
        
        Args:
            service_type: Service type
            
        Returns:
            Service instance if registered, None otherwise
            
        Raises:
            DependencyError: If service dependencies cannot be resolved
        """
        try:
            service = self.services.get(service_type)
            
            if service is None:
                error_context: ErrorContext = {
                    "operation": "get_service",
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "service_type": service_type.__name__,
                        "registered_services": [
                            t.__name__ for t in self.services.keys()
                        ]
                    }
                }
                raise DependencyError(
                    f"Service {service_type.__name__} not registered",
                    details=error_context
                )
            
            # Check if service has unresolved dependencies
            if hasattr(service, "__dependencies__"):
                deps = getattr(service, "__dependencies__")
                for dep in deps:
                    if dep not in self.services:
                        error_context = {
                            "operation": "get_service",
                            "timestamp": datetime.utcnow(),
                            "details": {
                                "service_type": service_type.__name__,
                                "missing_dependency": dep.__name__,
                                "registered_services": [
                                    t.__name__ for t in self.services.keys()
                                ]
                            }
                        }
                        raise DependencyError(
                            f"Missing dependency {dep.__name__} for service {service_type.__name__}",
                            details=error_context
                        )
            
            return cast(Optional[T], service)
            
        except DependencyError:
            raise
        except Exception as e:
            error_context = {
                "operation": "get_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "service_type": service_type.__name__,
                    "error": str(e)
                }
            }
            raise DependencyError(
                f"Failed to get service {service_type.__name__}: {str(e)}",
                details=error_context
            )
    
    def get_config(self):
        """Get configuration.
        
        Returns:
            Configuration object
        """
        return self.config

# Create singleton instance
service_provider = ServiceProvider()

__all__ = ['service_provider', 'ServiceLifetime']
