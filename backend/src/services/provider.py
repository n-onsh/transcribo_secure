"""Service provider for backend."""

import logging
import os
from typing import Optional, Dict, List, Type, TypeVar, Any
from azure.keyvault.keys import KeyClient
from azure.identity import DefaultAzureCredential
from ..utils.logging import log_info, log_error
from ..utils.exceptions import ConfigurationError
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
from .interfaces import (
    StorageInterface,
    JobManagerInterface,
    VocabularyInterface,
    ZipHandlerInterface,
    ViewerInterface,
    TagServiceInterface
)
from .tag_service import TagService

T = TypeVar('T')

from enum import Enum, auto
from dataclasses import dataclass
from typing import Callable, Dict, Optional, Set, Type, TypeVar, Any

class ServiceLifetime(Enum):
    """Service lifetime options."""
    SINGLETON = auto()  # One instance for entire application
    SCOPED = auto()    # One instance per scope (e.g. request)
    TRANSIENT = auto() # New instance each time

@dataclass
class ServiceRegistration:
    """Service registration information."""
    service_type: Type
    factory: Callable[[], Any]
    lifetime: ServiceLifetime
    dependencies: Set[Type]
    instance: Optional[Any] = None

class ServiceProvider:
    """Provider for backend services."""

    def __init__(self):
        """Initialize service provider."""
        self.settings = None
        self.initialized = False
        self._initializing = set()  # Track services being initialized to detect cycles
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._instances: Dict[Type, Any] = {}
        
        # Register core services
        self._register_core_services()

    def register(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.SINGLETON,
        dependencies: Set[Type] = None
    ) -> None:
        """Register a service."""
        self._registrations[service_type] = ServiceRegistration(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
            dependencies=dependencies or set()
        )

    def get(self, service_type: Type[T]) -> T:
        """Get a service instance."""
        if not self.initialized:
            raise RuntimeError("Service provider not initialized")
            
        # Check if service is registered
        registration = self._registrations.get(service_type)
        if not registration:
            raise ValueError(f"No service registered for type {service_type.__name__}")
            
        # Return existing instance for singletons
        if (registration.lifetime == ServiceLifetime.SINGLETON and 
            service_type in self._instances):
            return self._instances[service_type]
            
        # Detect circular dependencies
        if service_type in self._initializing:
            raise ValueError(f"Circular dependency detected for {service_type.__name__}")
            
        # Create new instance
        self._initializing.add(service_type)
        try:
            # Resolve dependencies first
            for dep_type in registration.dependencies:
                if dep_type not in self._instances:
                    self.get(dep_type)
                    
            # Create instance
            instance = registration.factory()
            
            # Store singleton instances
            if registration.lifetime == ServiceLifetime.SINGLETON:
                self._instances[service_type] = instance
                
            return instance
            
        finally:
            self._initializing.remove(service_type)

    def _register_core_services(self) -> None:
        """Register core services with their dependencies."""
        # Register settings first
        self.register(
            Dict[str, Any],
            lambda: self._load_settings(),
            ServiceLifetime.SINGLETON
        )
        
        # Register Azure Key Vault client
        self.register(
            KeyClient,
            lambda: KeyClient(
                vault_url=self.get(Dict[str, Any])['key_vault_url'],
                credential=DefaultAzureCredential()
            ),
            ServiceLifetime.SINGLETON
        )
        
        # Register core services with dependencies
        self.register(
            DatabaseService,
            lambda: DatabaseService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON
        )
        
        self.register(
            StorageService,
            lambda: StorageService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            KeyManagementService,
            lambda: KeyManagementService(
                self.get(Dict[str, Any]),
                self.get(KeyClient)
            ),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any], KeyClient}
        )
        
        self.register(
            EncryptionService,
            lambda: EncryptionService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            FileKeyService,
            lambda: FileKeyService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            DatabaseFileKeyService,
            lambda: DatabaseFileKeyService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            JobManager,
            lambda: JobManager(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            JobDistributionService,
            lambda: JobDistributionService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            TranscriptionService,
            lambda: TranscriptionService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            ZipHandlerService,
            lambda: ZipHandlerService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            ViewerService,
            lambda: ViewerService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
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
            lambda: FaultToleranceService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )
        
        self.register(
            TagService,
            lambda: TagService(self.get(DatabaseService)),
            ServiceLifetime.SINGLETON,
            {DatabaseService}
        )
        
        self.register(
            CleanupService,
            lambda: CleanupService(self.get(Dict[str, Any])),
            ServiceLifetime.SINGLETON,
            {Dict[str, Any]}
        )

    async def initialize(self):
        """Initialize services."""
        if self.initialized:
            return

        try:
            # Initialize settings
            self.settings = self.get(Dict[str, Any])
            log_info("Settings loaded")

            # Initialize all singleton services
            for registration in self._registrations.values():
                if registration.lifetime == ServiceLifetime.SINGLETON:
                    service = self.get(registration.service_type)
                    if hasattr(service, 'initialize'):
                        await service.initialize()
                        log_info(f"{registration.service_type.__name__} initialized")

            self.initialized = True
            log_info("Service provider initialization complete")

        except Exception as e:
            log_error(f"Failed to initialize service provider: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up services."""
        try:
            # Clean up all singleton services in reverse dependency order
            for registration in reversed(list(self._registrations.values())):
                if (registration.lifetime == ServiceLifetime.SINGLETON and
                    registration.service_type in self._instances):
                    service = self._instances[registration.service_type]
                    if hasattr(service, 'cleanup'):
                        await service.cleanup()
                        log_info(f"{registration.service_type.__name__} cleaned up")
            
            # Clear all instances
            self._instances.clear()
            self.initialized = False
            log_info("Service provider cleanup complete")

        except Exception as e:
            log_error(f"Error during service provider cleanup: {str(e)}")
            raise

    def _load_settings(self) -> Dict:
        """Load settings from environment."""
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

# Global service provider instance
service_provider = ServiceProvider()
