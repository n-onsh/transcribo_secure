import logging
from typing import Dict, Optional, Type, TypeVar
from .interfaces import (
    StorageInterface,
    JobManagerInterface,
    DatabaseInterface,
    KeyManagementInterface,
    EncryptionInterface
)
from .storage import StorageService
from .database import DatabaseService
from .job_manager import JobManager
from .key_management import KeyManagementService
from .encryption import EncryptionService
from ..utils.metrics import track_time, DB_OPERATION_DURATION

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ServiceProvider:
    """Service provider for dependency injection"""
    
    def __init__(self):
        """Initialize service provider"""
        self._services: Dict[Type, object] = {}
        self._initialized = False
        logger.info("Service provider initialized")

    @track_time(DB_OPERATION_DURATION, {"operation": "initialize_services"})
    async def initialize(self):
        """Initialize all services in correct order"""
        if self._initialized:
            return

        try:
            # Initialize database first
            db = await self._init_database()
            self._services[DatabaseInterface] = db

            # Initialize key management and encryption
            key_mgmt = await self._init_key_management()
            self._services[KeyManagementInterface] = key_mgmt

            encryption = await self._init_encryption(key_mgmt)
            self._services[EncryptionInterface] = encryption

            # Initialize storage
            storage = await self._init_storage(db, encryption)
            self._services[StorageInterface] = storage

            # Initialize job manager last
            job_manager = await self._init_job_manager(db, storage)
            self._services[JobManagerInterface] = job_manager

            self._initialized = True
            logger.info("All services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Clean up all services"""
        try:
            # Get services that need cleanup
            db = self.get(DatabaseInterface)
            if db:
                await db.close()

            self._services.clear()
            self._initialized = False
            logger.info("Services cleaned up")

        except Exception as e:
            logger.error(f"Error cleaning up services: {str(e)}")
            raise

    def get(self, service_type: Type[T]) -> Optional[T]:
        """Get service by type"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._services.get(service_type)

    async def _init_database(self) -> DatabaseInterface:
        """Initialize database service"""
        try:
            db = DatabaseService()
            await db.initialize_database()
            return db
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    async def _init_key_management(self) -> KeyManagementInterface:
        """Initialize key management service"""
        try:
            key_mgmt = KeyManagementService()
            # No async initialization needed
            return key_mgmt
        except Exception as e:
            logger.error(f"Failed to initialize key management: {str(e)}")
            raise

    async def _init_encryption(
        self,
        key_mgmt: KeyManagementInterface
    ) -> EncryptionInterface:
        """Initialize encryption service"""
        try:
            encryption = EncryptionService()
            # No async initialization needed
            return encryption
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise

    async def _init_storage(
        self,
        db: DatabaseInterface,
        encryption: EncryptionInterface
    ) -> StorageInterface:
        """Initialize storage service"""
        try:
            storage = StorageService(
                database_service=db,
                encryption_service=encryption
            )
            await storage._init_buckets()
            return storage
        except Exception as e:
            logger.error(f"Failed to initialize storage: {str(e)}")
            raise

    async def _init_job_manager(
        self,
        db: DatabaseInterface,
        storage: StorageInterface
    ) -> JobManagerInterface:
        """Initialize job manager service"""
        try:
            job_manager = JobManager(
                storage=storage,
                db=db
            )
            await job_manager.start()
            return job_manager
        except Exception as e:
            logger.error(f"Failed to initialize job manager: {str(e)}")
            raise
