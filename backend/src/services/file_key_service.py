from typing import Optional, List
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from uuid import UUID
from .database import DatabaseService
from .database_file_keys import DatabaseFileKeyService
from ..models.file_key import (
    FileKey,
    FileKeyShare,
    FileKeyCreate,
    FileKeyShareCreate,
    FileKeyUpdate,
    FileKeyShareUpdate
)

logger = logs.get_logger(__name__)

class FileKeyService:
    def __init__(self):
        """Initialize file key service"""
        try:
            self.db = DatabaseService()
            self.db_service = DatabaseFileKeyService(self.db.pool)
            logger.emit(
                "File key service initialized",
                severity=Severity.INFO
            )
        except Exception as e:
            logger.emit(
                "Failed to initialize file key service",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    async def create_file_key(self, file_key: FileKeyCreate) -> FileKey:
        """Create file key"""
        return await self.db_service.create_file_key(file_key)

    async def get_file_key(self, file_id: UUID) -> Optional[FileKey]:
        """Get file key"""
        return await self.db_service.get_file_key(file_id)

    async def update_file_key(
        self,
        file_id: UUID,
        update: FileKeyUpdate
    ) -> Optional[FileKey]:
        """Update file key"""
        return await self.db_service.update_file_key(file_id, update)

    async def delete_file_key(self, file_id: UUID) -> bool:
        """Delete file key and all its shares"""
        try:
            # First delete all shares
            await self.db_service.delete_all_file_key_shares(file_id)
            # Then delete the key itself
            return await self.db_service.delete_file_key(file_id)
        except Exception as e:
            logger.emit(
                "Failed to delete file key",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_id": str(file_id)
                }
            )
            raise

    async def share_file_key(
        self,
        share: FileKeyShareCreate
    ) -> FileKeyShare:
        """Share file key with user"""
        return await self.db_service.create_file_key_share(share)

    async def get_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> Optional[FileKeyShare]:
        """Get file key share"""
        return await self.db_service.get_file_key_share(file_id, user_id)

    async def list_file_key_shares(
        self,
        file_id: UUID
    ) -> List[FileKeyShare]:
        """List all shares for a file key"""
        return await self.db_service.list_file_key_shares(file_id)

    async def update_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID,
        update: FileKeyShareUpdate
    ) -> Optional[FileKeyShare]:
        """Update file key share"""
        return await self.db_service.update_file_key_share(file_id, user_id, update)

    async def revoke_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> bool:
        """Revoke file key share from user"""
        return await self.db_service.delete_file_key_share(file_id, user_id)

    async def get_shared_files(self, user_id: UUID) -> List[FileKey]:
        """Get all files shared with user"""
        try:
            async with self.db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT fk.* 
                    FROM file_keys fk
                    JOIN file_key_shares fks ON fk.file_id = fks.file_id
                    WHERE fks.user_id = $1
                    ORDER BY fks.created_at DESC
                    """,
                    user_id
                )
                return [FileKey(**dict(row)) for row in rows]
        except Exception as e:
            logger.emit(
                "Failed to get shared files",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "user_id": str(user_id)
                }
            )
            raise

    async def get_file_access(self, file_id: UUID) -> dict:
        """Get file access information including owner and shared users"""
        try:
            async with self.db.pool.acquire() as conn:
                # Get file key record
                file_key = await self.get_file_key(file_id)
                if not file_key:
                    return None

                # Get shares
                shares = await self.list_file_key_shares(file_id)
                shared_with = [share.user_id for share in shares]

                return {
                    "file_id": file_id,
                    "owner_id": file_key.owner_id,
                    "shared_with": shared_with
                }
        except Exception as e:
            logger.emit(
                "Failed to get file access info",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_id": str(file_id)
                }
            )
            raise
