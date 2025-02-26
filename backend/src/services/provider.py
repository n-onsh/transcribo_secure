"""Service provider for backend."""

import logging
import os
from typing import Optional, Dict, List, Type, TypeVar, Any, Set, Callable, cast
from datetime import datetime
from azure.keyvault.keys import KeyClient
from azure.identity import DefaultAzureCredential
from ..utils.logging import log_info, log_error
from ..utils.exceptions import ConfigurationError, TranscriboError
from ..types import (
    ServiceConfig,
    ErrorContext,
    ServiceProtocol,
    Result
)
from .database import DatabaseService
from .storage import StorageService
from .encryption import EncryptionService
from .job_manager import JobManager
from .key_management import KeyManagementService
from .file_key_service import FileKeyService
from .database_file_keys import DatabaseFileKeyService
from .zip_handler import ZipHandlerService
from .viewer import ViewerService
from .vocabulary import VocabularyService
from .fault_tolerance import FaultToleranceService
from .job_distribution import JobDistributionService
from .cleanup import CleanupService
from .transcription import TranscriptionService
from .tag_service import TagService

T = TypeVar('T')
ServiceType = TypeVar('ServiceType', bound=ServiceProtocol)

class ServiceLifetime:
    """Service lifetime options."""
    SINGLETON = "singleton"  # One instance for entire application
    SCOPED = "scoped"       # One instance per scope (e.g. request)
    TRANSIENT = "transient" # New instance each time

class ServiceRegistration(TypedDict):
    """Service registration information."""
    service_type: Type[ServiceType]
    factory: Callable[[], ServiceType]
    lifetime: str
    dependencies: Set[Type[ServiceType]]
    instance: Optional[ServiceType]

class ServiceProvider:
    """Provider for backend services."""

    def __init__(self) -> None:
        """Initialize service provider."""
        self.settings: Optional[ServiceConfig] = None
        self.initialized: bool = False
        self._initializing: Set[Type[ServiceType]] = set()  # Track services being initialized
        self._registrations: Dict[Type[ServiceType], ServiceRegistration] = {}
        self._instances: Dict[Type[ServiceType], ServiceType] = {}
        
        # Register core services
        self._register_core_services()

    def register(
        self,
        service_type: Type[ServiceType],
        factory: Callable[[], ServiceType],
        lifetime: str = ServiceLifetime.SINGLETON,
        dependencies: Optional[Set[Type[ServiceType]]] = None
    ) -> None:
        """Register a service.
        
        Args:
            service_type: Type of service to register
            factory: Factory function to create service instance
            lifetime: Service lifetime (singleton, scoped, or transient)
            dependencies: Set of service dependencies
        """
        self._registrations[service_type] = {
            "service_type": service_type,
            "factory": factory,
            "lifetime": lifetime,
            "dependencies": dependencies or set(),
            "instance": None
        }

    def get(self, service_type: Type[ServiceType]) -> ServiceType:
        """Get a service instance.
        
        Args:
            service_type: Type of service to get
            
        Returns:
            Service instance
            
        Raises:
            RuntimeError: If service provider not initialized
            ValueError: If service not registered or circular dependency detected
            TranscriboError: If service creation fails
        """
        if not self.initialized:
            raise RuntimeError("Service provider not initialized")
            
        # Check if service is registered
        registration = self._registrations.get(service_type)
        if not registration:
            raise ValueError(f"No service registered for type {service_type.__name__}")
            
        # Return existing instance for singletons
        if (registration["lifetime"] == ServiceLifetime.SINGLETON and 
            service_type in self._instances):
            return self._instances[service_type]
            
        # Detect circular dependencies
        if service_type in self._initializing:
            raise ValueError(f"Circular dependency detected for {service_type.__name__}")
            
        # Create new instance
        self._initializing.add(service_type)
        try:
            # Resolve dependencies first
            for dep_type in registration["dependencies"]:
                if dep_type not in self._instances:
                    self.get(cast(Type[ServiceType], dep_type))
                    
            # Create instance
            instance = registration["factory"]()
            
            # Store singleton instances
            if registration["lifetime"] == ServiceLifetime.SINGLETON:
                self._instances[service_type] = instance
                
            return instance
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_service",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "service_type": service_type.__name__
                }
            }
            raise TranscriboError(
                f"Failed to create service {service_type.__name__}",
                details=error_context
            )
        finally:
            self._initializing.remove(service_type)

    def _register_core_services(self) -> None:
        """Register core services with their dependencies."""
        # Register settings first
        self.register(
            cast(Type[ServiceType], Dict[str, Any]),
            lambda: self._load_settings(),
            ServiceLifetime.SINGLETON
        )
        
        # Register Azure Key Vault client
        self.register(
            cast(Type[ServiceType], KeyClient),
            lambda: KeyClient(
                vault_url=self.get(cast(Type[ServiceType], Dict[str, Any]))['key_vault_url'],
                credential=DefaultAzureCredential()
            ),
            ServiceLifetime.SINGLETON
        )
        
        # Register core services with dependencies
        self.register(
            DatabaseService,
            lambda: DatabaseService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            StorageService,
            lambda: StorageService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            KeyManagementService,
            lambda: KeyManagementService(
                self.get(cast(Type[ServiceType], Dict[str, Any])),
                self.get(cast(Type[ServiceType], KeyClient))
            ),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any]), cast(Type[ServiceType], KeyClient)}
        )
        
        self.register(
            EncryptionService,
            lambda: EncryptionService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            FileKeyService,
            lambda: FileKeyService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            DatabaseFileKeyService,
            lambda: DatabaseFileKeyService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            JobManager,
            lambda: JobManager(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            JobDistributionService,
            lambda: JobDistributionService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            TranscriptionService,
            lambda: TranscriptionService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            ZipHandlerService,
            lambda: ZipHandlerService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            ViewerService,
            lambda: ViewerService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            VocabularyService,
            lambda: VocabularyService(
                self.get(JobManager),
                self.get(TranscriptionService)
            ),
            ServiceLifetime.SINGLETON,
            {JobManager, TranscriptionService}
        )
        
        self.register(
            FaultToleranceService,
            lambda: FaultToleranceService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )
        
        self.register(
            TagService,
            lambda: TagService(self.get(DatabaseService)),
            ServiceLifetime.SINGLETON,
            {DatabaseService}
        )
        
        self.register(
            CleanupService,
            lambda: CleanupService(self.get(cast(Type[ServiceType], Dict[str, Any]))),
            ServiceLifetime.SINGLETON,
            {cast(Type[ServiceType], Dict[str, Any])}
        )

    async def initialize(self) -> None:
        """Initialize services.
        
        Raises:
            TranscriboError: If initialization fails
        """
        if self.initialized:
            return

        try:
            # Initialize settings
            self.settings = cast(ServiceConfig, self.get(cast(Type[ServiceType], Dict[str, Any])))
            log_info("Settings loaded")

            # Initialize all singleton services
            for registration in self._registrations.values():
                if registration["lifetime"] == ServiceLifetime.SINGLETON:
                    service = self.get(registration["service_type"])
                    if hasattr(service, 'initialize'):
                        await service.initialize()
                        log_info(f"{registration['service_type'].__name__} initialized")

            self.initialized = True
            log_info("Service provider initialization complete")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_provider",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize service provider: {str(e)}")
            raise TranscriboError(
                "Failed to initialize service provider",
                details=error_context
            )

    async def cleanup(self) -> None:
        """Clean up services.
        
        Raises:
            TranscriboError: If cleanup fails
        """
        try:
            # Clean up all singleton services in reverse dependency order
            for registration in reversed(list(self._registrations.values())):
                if (registration["lifetime"] == ServiceLifetime.SINGLETON and
                    registration["service_type"] in self._instances):
                    service = self._instances[registration["service_type"]]
                    if hasattr(service, 'cleanup'):
                        await service.cleanup()
                        log_info(f"{registration['service_type'].__name__} cleaned up")
            
            # Clear all instances
            self._instances.clear()
            self.initialized = False
            log_info("Service provider cleanup complete")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_provider",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during service provider cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up service provider",
                details=error_context
            )

    def _load_settings(self) -> ServiceConfig:
        """Load settings from environment.
        
        Returns:
            Service configuration
            
        Raises:
            ConfigurationError: If required settings are missing
        """
        try:
            # Get required Azure Key Vault settings
            key_vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            if not key_vault_url:
                raise ConfigurationError("AZURE_KEY_VAULT_URL environment variable is required")

            return {
                'database_url': os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/db'),
                'storage_path': os.getenv('STORAGE_PATH', '/data'),
                'temp_dir': os.getenv('TEMP_DIR', '/tmp'),
                'cache_dir': os.getenv('CACHE_DIR', '/cache'),
                'max_file_size': int(os.getenv('MAX_FILE_SIZE', '104857600')),  # 100MB
                'allowed_extensions': os.getenv('ALLOWED_EXTENSIONS', '.mp3,.wav,.m4a').split(','),
                'cleanup_interval': int(os.getenv('CLEANUP_INTERVAL', '3600')),  # 1 hour
                'job_timeout': int(os.getenv('JOB_TIMEOUT', '3600')),  # 1 hour
                'retry_limit': int(os.getenv('RETRY_LIMIT', '3')),
                'worker_count': int(os.getenv('WORKER_COUNT', '4')),
                # Key management settings
                'key_vault_url': key_vault_url,
                'key_rotation_interval': int(os.getenv('KEY_ROTATION_INTERVAL', '86400')),  # 24 hours
                'max_key_age': int(os.getenv('MAX_KEY_AGE', '2592000')),  # 30 days
                'min_key_length': int(os.getenv('MIN_KEY_LENGTH', '32'))
            }
        except ValueError as e:
            error_context: ErrorContext = {
                "operation": "load_settings",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            raise ConfigurationError(
                "Invalid environment variable value",
                details=error_context
            )
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "load_settings",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            raise ConfigurationError(
                "Failed to load settings",
                details=error_context
            )

# Global service provider instance
service_provider = ServiceProvider()
