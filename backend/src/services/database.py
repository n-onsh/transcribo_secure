import os
import logging
from typing import Optional, List, Dict
import asyncpg
from datetime import datetime, timedelta
import uuid
from ..models.user import User
from ..models.job import Job, JobStatus
from ..models.vocabulary import VocabularyList
from ..models.file_key import (
    FileKey,
    FileKeyShare,
    FileKeyCreate,
    FileKeyShareCreate,
    FileKeyUpdate,
    FileKeyShareUpdate
)
from .database_file_keys import DatabaseFileKeyService
from ..utils.metrics import (
    DB_OPERATION_DURATION,
    DB_OPERATION_ERRORS,
    DB_CONNECTIONS,
    track_time,
    track_errors,
    update_gauge
)

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        """Initialize database service"""
        # Get configuration
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "transcribo")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD")

        if not self.password:
            raise ValueError("POSTGRES_PASSWORD environment variable not set")

        # Initialize connection pool
        self.pool = None
        
        # Initialize file key service
        self.file_keys = None

        logger.info("Database service initialized")

    @track_time(DB_OPERATION_DURATION, {"operation": "initialize"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "initialize", "error_type": "unknown"})
    async def initialize_database(self):
        """Initialize database connection and schema"""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=5,
                max_size=20
            )

            # Initialize file key service
            self.file_keys = DatabaseFileKeyService(self.pool)

            # Update connection metrics
            update_gauge(DB_CONNECTIONS, len(self.pool._holders))

            logger.info("Database initialized")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    # File key operations
    async def create_file_key(self, file_key: FileKeyCreate) -> FileKey:
        """Create file key"""
        return await self.file_keys.create_file_key(file_key)

    async def get_file_key(self, file_id: uuid.UUID) -> Optional[FileKey]:
        """Get file key"""
        return await self.file_keys.get_file_key(file_id)

    async def update_file_key(
        self,
        file_id: uuid.UUID,
        update: FileKeyUpdate
    ) -> Optional[FileKey]:
        """Update file key"""
        return await self.file_keys.update_file_key(file_id, update)

    async def delete_file_key(self, file_id: uuid.UUID) -> bool:
        """Delete file key"""
        return await self.file_keys.delete_file_key(file_id)

    async def create_file_key_share(
        self,
        share: FileKeyShareCreate
    ) -> FileKeyShare:
        """Create file key share"""
        return await self.file_keys.create_file_key_share(share)

    async def get_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[FileKeyShare]:
        """Get file key share"""
        return await self.file_keys.get_file_key_share(file_id, user_id)

    async def list_file_key_shares(
        self,
        file_id: uuid.UUID
    ) -> List[FileKeyShare]:
        """List file key shares"""
        return await self.file_keys.list_file_key_shares(file_id)

    async def update_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
        update: FileKeyShareUpdate
    ) -> Optional[FileKeyShare]:
        """Update file key share"""
        return await self.file_keys.update_file_key_share(file_id, user_id, update)

    async def delete_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Delete file key share"""
        return await self.file_keys.delete_file_key_share(file_id, user_id)

    async def delete_all_file_key_shares(self, file_id: uuid.UUID) -> int:
        """Delete all file key shares for a file"""
        return await self.file_keys.delete_all_file_key_shares(file_id)

    async def get_active_connections(self) -> int:
        """Get number of active database connections"""
        if not self.pool:
            return 0
        return len(self.pool._holders)

    # Rest of the original DatabaseService implementation...
    # [Previous methods remain unchanged]
