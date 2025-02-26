"""FastAPI dependency functions."""

from typing import Annotated, Type, TypeVar
from fastapi import Depends, Request
from ..services.provider import ServiceProvider, service_provider, ServiceLifetime

T = TypeVar('T')

def get_provider(request: Request) -> ServiceProvider:
    """Get service provider instance."""
    return service_provider

def get_service(service_type: Type[T]) -> T:
    """Get a service instance."""
    def _get_service(provider: ServiceProvider = Depends(get_provider)) -> T:
        return provider.get(service_type)
    return Depends(_get_service)

def get_scoped_service(service_type: Type[T]) -> T:
    """Get a scoped service instance."""
    def _get_scoped_service(
        request: Request,
        provider: ServiceProvider = Depends(get_provider)
    ) -> T:
        # Check if service is already created for this request
        if not hasattr(request.state, 'services'):
            request.state.services = {}
            
        if service_type not in request.state.services:
            # Get service registration
            registration = provider._registrations.get(service_type)
            if not registration:
                raise ValueError(f"No service registered for type {service_type.__name__}")
                
            if registration.lifetime != ServiceLifetime.SCOPED:
                raise ValueError(f"Service {service_type.__name__} is not scoped")
                
            # Create new instance for this request
            instance = provider.get(service_type)
            request.state.services[service_type] = instance
            
        return request.state.services[service_type]
    return Depends(_get_scoped_service)

# Common service dependencies
DatabaseService = Annotated[
    "DatabaseService",
    Depends(get_service("DatabaseService"))
]

StorageService = Annotated[
    "StorageService",
    Depends(get_service("StorageService"))
]

JobManager = Annotated[
    "JobManager",
    Depends(get_service("JobManager"))
]

TranscriptionService = Annotated[
    "TranscriptionService",
    Depends(get_service("TranscriptionService"))
]

TagService = Annotated[
    "TagService",
    Depends(get_service("TagService"))
]

VocabularyService = Annotated[
    "VocabularyService",
    Depends(get_service("VocabularyService"))
]

ZipHandlerService = Annotated[
    "ZipHandlerService",
    Depends(get_service("ZipHandlerService"))
]

ViewerService = Annotated[
    "ViewerService",
    Depends(get_service("ViewerService"))
]
