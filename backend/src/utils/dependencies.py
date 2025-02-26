"""FastAPI dependency functions."""

from typing import Annotated, Type, TypeVar, Dict, Any, cast
from datetime import datetime
from fastapi import Depends, Request
from ..services.provider import ServiceProvider, service_provider, ServiceLifetime
from ..types import (
    ServiceProtocol,
    ErrorContext,
    ServiceConfig
)
from ..utils.exceptions import DependencyError, TranscriboError
from ..utils.logging import log_error

T = TypeVar('T')
ServiceType = TypeVar('ServiceType', bound=ServiceProtocol)

def get_provider(request: Request) -> ServiceProvider:
    """Get service provider instance.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Service provider instance
    """
    return service_provider

def get_service(service_type: Type[ServiceType]) -> ServiceType:
    """Get a service instance.
    
    Args:
        service_type: Type of service to get
        
    Returns:
        Service instance
        
    Raises:
        DependencyError: If service cannot be retrieved
    """
    def _get_service(provider: ServiceProvider = Depends(get_provider)) -> ServiceType:
        try:
            return provider.get(service_type)
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "service_type": service_type.__name__
                }
            }
            log_error(f"Failed to get service {service_type.__name__}: {str(e)}")
            raise DependencyError(
                f"Failed to get service {service_type.__name__}",
                details=error_context
            )
    return Depends(_get_service)

def get_scoped_service(service_type: Type[ServiceType]) -> ServiceType:
    """Get a scoped service instance.
    
    Args:
        service_type: Type of service to get
        
    Returns:
        Service instance
        
    Raises:
        DependencyError: If service cannot be retrieved or is not scoped
    """
    def _get_scoped_service(
        request: Request,
        provider: ServiceProvider = Depends(get_provider)
    ) -> ServiceType:
        try:
            # Check if service is already created for this request
            if not hasattr(request.state, 'services'):
                request.state.services = {}
                
            if service_type not in request.state.services:
                # Get service registration
                registration = provider._registrations.get(service_type)
                if not registration:
                    raise DependencyError(f"No service registered for type {service_type.__name__}")
                    
                if registration["lifetime"] != ServiceLifetime.SCOPED:
                    raise DependencyError(f"Service {service_type.__name__} is not scoped")
                    
                # Create new instance for this request
                instance = provider.get(service_type)
                request.state.services[service_type] = instance
                
            return cast(ServiceType, request.state.services[service_type])
            
        except DependencyError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_scoped_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "service_type": service_type.__name__
                }
            }
            log_error(f"Failed to get scoped service {service_type.__name__}: {str(e)}")
            raise DependencyError(
                f"Failed to get scoped service {service_type.__name__}",
                details=error_context
            )
    return Depends(_get_scoped_service)

def validate_service_dependencies(
    service_type: Type[ServiceType],
    provider: ServiceProvider
) -> None:
    """Validate service dependencies.
    
    Args:
        service_type: Type of service to validate
        provider: Service provider instance
        
    Raises:
        DependencyError: If dependencies are invalid
    """
    try:
        # Get service registration
        registration = provider._registrations.get(service_type)
        if not registration:
            raise DependencyError(f"No service registered for type {service_type.__name__}")
            
        # Check each dependency
        for dep_type in registration["dependencies"]:
            if dep_type not in provider._registrations:
                raise DependencyError(
                    f"Missing dependency {dep_type.__name__} for service {service_type.__name__}"
                )
                
            # Recursively validate dependencies
            validate_service_dependencies(cast(Type[ServiceType], dep_type), provider)
            
    except DependencyError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "validate_dependencies",
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "service_type": service_type.__name__
            }
        }
        log_error(f"Failed to validate dependencies for {service_type.__name__}: {str(e)}")
        raise DependencyError(
            f"Failed to validate dependencies for {service_type.__name__}",
            details=error_context
        )

# Import services
from ..services.database import DatabaseService
from ..services.storage import StorageService
from ..services.job_manager import JobManager
from ..services.transcription import TranscriptionService
from ..services.tag_service import TagService
from ..services.vocabulary import VocabularyService
from ..services.zip_handler import ZipHandlerService
from ..services.viewer import ViewerService

# Common service dependencies
DatabaseServiceDep = Annotated[
    DatabaseService,
    Depends(get_service(DatabaseService))
]

StorageServiceDep = Annotated[
    StorageService,
    Depends(get_service(StorageService))
]

JobManagerDep = Annotated[
    JobManager,
    Depends(get_service(JobManager))
]

TranscriptionServiceDep = Annotated[
    TranscriptionService,
    Depends(get_service(TranscriptionService))
]

TagServiceDep = Annotated[
    TagService,
    Depends(get_service(TagService))
]

VocabularyServiceDep = Annotated[
    VocabularyService,
    Depends(get_service(VocabularyService))
]

ZipHandlerServiceDep = Annotated[
    ZipHandlerService,
    Depends(get_service(ZipHandlerService))
]

ViewerServiceDep = Annotated[
    ViewerService,
    Depends(get_service(ViewerService))
]
