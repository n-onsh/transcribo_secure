"""Service provider for backend."""

import logging
from typing import Optional, Dict, List, Type, TypeVar, Any
from ..utils.logging import log_info, log_error
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

class ServiceProvider:
    """Provider for backend services."""

    def __init__(self):
        """Initialize service provider."""
        self.settings = None
        self.database = None
        self.storage: Optional[StorageService] = None
        self.encryption = None
        self.job_manager: Optional[JobManager] = None
        self.key_management = None
        self.file_key_service = None
        self.database_file_keys = None
        self.zip_handler: Optional[ZipHandlerService] = None
        self.viewer: Optional[ViewerService] = None
        self.vocabulary: Optional[VocabularyService] = None
        self.fault_tolerance = None
        self.job_distribution = None
        self.cleanup = None
        self.transcription: Optional[TranscriptionService] = None
        self.tag_service: Optional[TagService] = None
        self.initialized = False

        # Interface mappings
        self._interface_mappings = {
            StorageInterface: lambda: self.storage,
            JobManagerInterface: lambda: self.job_manager,
            VocabularyInterface: lambda: self.vocabulary,
            ZipHandlerInterface: lambda: self.zip_handler,
            ViewerInterface: lambda: self.viewer,
            TagServiceInterface: lambda: self.tag_service
        }

    def get(self, interface: Type[T]) -> Optional[T]:
        """Get a service by its interface."""
        if not self.initialized:
            raise RuntimeError("Service provider not initialized")
        
        getter = self._interface_mappings.get(interface)
        if not getter:
            raise ValueError(f"No service registered for interface {interface.__name__}")
        
        return getter()

    async def initialize(self):
        """Initialize services."""
        if self.initialized:
            return

        try:
            # Initialize settings
            self.settings = self._load_settings()
            log_info("Settings loaded")

            # Initialize core services
            self.database = DatabaseService(self.settings)
            await self.database.initialize()
            log_info("Database service initialized")

            self.storage = StorageService(self.settings)
            await self.storage.initialize()
            log_info("Storage service initialized")

            self.encryption = EncryptionService(self.settings)
            await self.encryption.initialize()
            log_info("Encryption service initialized")

            # Initialize key services
            self.key_management = KeyManagementService(self.settings)
            await self.key_management.initialize()
            log_info("Key management service initialized")

            self.file_key_service = FileKeyService(self.settings)
            await self.file_key_service.initialize()
            log_info("File key service initialized")

            self.database_file_keys = DatabaseFileKeyService(self.settings)
            await self.database_file_keys.initialize()
            log_info("Database file keys service initialized")

            # Initialize job services
            self.job_manager = JobManager(self.settings)
            await self.job_manager.initialize()
            log_info("Job manager initialized")

            self.job_distribution = JobDistributionService(self.settings)
            await self.job_distribution.initialize()
            log_info("Job distribution service initialized")

            # Initialize transcription service
            self.transcription = TranscriptionService(self.settings)
            await self.transcription.initialize()
            log_info("Transcription service initialized")

            # Initialize file handling services
            self.zip_handler = ZipHandlerService()
            await self.zip_handler.initialize()
            log_info("ZIP handler initialized")

            self.viewer = ViewerService(self.settings)
            await self.viewer.initialize()
            log_info("Viewer service initialized")

            # Initialize auxiliary services
            self.vocabulary = VocabularyService(self.job_manager, self.transcription)
            await self.vocabulary.initialize()
            log_info("Vocabulary service initialized")

            self.fault_tolerance = FaultToleranceService(self.settings)
            await self.fault_tolerance.initialize()
            log_info("Fault tolerance service initialized")

            # Initialize tag service
            self.tag_service = TagService(self.database)
            await self.tag_service.initialize()
            log_info("Tag service initialized")

            self.cleanup = CleanupService(self.settings)
            await self.cleanup.initialize()
            log_info("Cleanup service initialized")

            self.initialized = True
            log_info("Service provider initialization complete")

        except Exception as e:
            log_error(f"Failed to initialize service provider: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up services."""
        try:
            if self.tag_service:
                await self.tag_service.cleanup()
                log_info("Tag service cleaned up")

            if self.cleanup:
                await self.cleanup.cleanup()
                log_info("Cleanup service cleaned up")

            if self.fault_tolerance:
                await self.fault_tolerance.cleanup()
                log_info("Fault tolerance service cleaned up")

            if self.vocabulary:
                await self.vocabulary.cleanup()
                log_info("Vocabulary service cleaned up")

            if self.viewer:
                await self.viewer.cleanup()
                log_info("Viewer service cleaned up")

            if self.zip_handler:
                await self.zip_handler.cleanup()
                log_info("ZIP handler cleaned up")

            if self.job_distribution:
                await self.job_distribution.cleanup()
                log_info("Job distribution service cleaned up")

            if self.transcription:
                await self.transcription.cleanup()
                log_info("Transcription service cleaned up")

            if self.job_manager:
                await self.job_manager.cleanup()
                log_info("Job manager cleaned up")

            if self.database_file_keys:
                await self.database_file_keys.cleanup()
                log_info("Database file keys service cleaned up")

            if self.file_key_service:
                await self.file_key_service.cleanup()
                log_info("File key service cleaned up")

            if self.key_management:
                await self.key_management.cleanup()
                log_info("Key management service cleaned up")

            if self.encryption:
                await self.encryption.cleanup()
                log_info("Encryption service cleaned up")

            if self.storage:
                await self.storage.cleanup()
                log_info("Storage service cleaned up")

            if self.database:
                await self.database.cleanup()
                log_info("Database service cleaned up")

            self.initialized = False
            log_info("Service provider cleanup complete")

        except Exception as e:
            log_error(f"Error during service provider cleanup: {str(e)}")
            raise

    def _load_settings(self) -> Dict:
        """Load settings from environment."""
        import os

        return {
            'database_url': os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/db'),
            'storage_path': os.getenv('STORAGE_PATH', '/data'),
            'encryption_key': os.getenv('ENCRYPTION_KEY', 'default-key'),
            'temp_dir': os.getenv('TEMP_DIR', '/tmp'),
            'cache_dir': os.getenv('CACHE_DIR', '/cache'),
            'max_file_size': int(os.getenv('MAX_FILE_SIZE', '104857600')),  # 100MB
            'allowed_extensions': os.getenv('ALLOWED_EXTENSIONS', '.mp3,.wav,.m4a').split(','),
            'cleanup_interval': int(os.getenv('CLEANUP_INTERVAL', '3600')),  # 1 hour
            'job_timeout': int(os.getenv('JOB_TIMEOUT', '3600')),  # 1 hour
            'retry_limit': int(os.getenv('RETRY_LIMIT', '3')),
            'worker_count': int(os.getenv('WORKER_COUNT', '4'))
        }

# Global service provider instance
service_provider = ServiceProvider()
