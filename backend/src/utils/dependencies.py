"""FastAPI dependency functions."""

from typing import Annotated, Type, TypeVar, Dict, Any, cast
from datetime import datetime
from fastapi import Depends, Request
from ..services.provider import ServiceProvider, service_provider, ServiceLifetime
from ..types import (
    ServiceProtocol,
    ErrorContext
)
from ..utils.exceptions import DependencyError
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
    def _get_service(
        request: Request,
        provider: ServiceProvider = Depends(get_provider)
    ) -> ServiceType:
        try:
            # Add request ID to error context if available
            request_id = getattr(request.state, "request_id", None)
            
            service = provider.get(service_type)
            if service is None:
                error_context: ErrorContext = {
                    "operation": "get_service",
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "service_type": service_type.__name__,
                        "request_id": request_id
                    }
                }
                raise DependencyError(
                    f"Service {service_type.__name__} not found",
                    details=error_context
                )
            return service
            
        except DependencyError:
            raise
        except Exception as e:
            error_context = {
                "operation": "get_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "service_type": service_type.__name__,
                    "request_id": request_id
                }
            }
            log_error(f"Failed to get service {service_type.__name__}: {str(e)}")
            raise DependencyError(
                f"Failed to get service {service_type.__name__}",
                details=error_context
            )
    return Depends(_get_service)

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
