import logging
from typing import Optional, List
from uuid import UUID
import asyncpg
from ..models.file_key import (
    FileKey,
    FileKeyShare,
    FileKeyCreate,
    FileKeyShareCreate,
    FileKeyUpdate,
    FileKeyShareUpdate
)

logger = logging.getLogger(__name__)

class DatabaseFileKeyService:
    def __init__(self, pool: asyncpg.Pool):
        """Initialize database file key service"""
        self.pool = pool

    async def create_file_key(self, file_key: FileKeyCreate) -> FileKey:
        """Create file key"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO file_keys (file_id, encrypted_key)
                    VALUES ($1, $2)
                    RETURNING *
                    """,
                    file_key.file_id,
                    file_key.encrypted_key
                )
                return FileKey(**dict(row))
        except Exception as e:
            logger.error(f"Failed to create file key: {str(e)}")
            raise

    async def get_file_key(self, file_id: UUID) -> Optional[FileKey]:
        """Get file key"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM file_keys
                    WHERE file_id = $1
                    """,
                    file_id
                )
                return FileKey(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Failed to get file key: {str(e)}")
            raise

    async def update_file_key(
        self,
        file_id: UUID,
        update: FileKeyUpdate
    ) -> Optional[FileKey]:
        """Update file key"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE file_keys
                    SET encrypted_key = COALESCE($2, encrypted_key)
                    WHERE file_id = $1
                    RETURNING *
                    """,
                    file_id,
                    update.encrypted_key
                )
                return FileKey(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Failed to update file key: {str(e)}")
            raise

    async def delete_file_key(self, file_id: UUID) -> bool:
        """Delete file key"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM file_keys
                    WHERE file_id = $1
                    """,
                    file_id
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete file key: {str(e)}")
            raise

    async def create_file_key_share(
        self,
        share: FileKeyShareCreate
    ) -> FileKeyShare:
        """Create file key share"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO file_key_shares (file_id, user_id, encrypted_key)
                    VALUES ($1, $2, $3)
                    RETURNING *
                    """,
                    share.file_id,
                    share.user_id,
                    share.encrypted_key
                )
                return FileKeyShare(**dict(row))
        except Exception as e:
            logger.error(f"Failed to create file key share: {str(e)}")
            raise

    async def get_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> Optional[FileKeyShare]:
        """Get file key share"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT * FROM file_key_shares
                    WHERE file_id = $1 AND user_id = $2
                    """,
                    file_id,
                    user_id
                )
                return FileKeyShare(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Failed to get file key share: {str(e)}")
            raise

    async def list_file_key_shares(
        self,
        file_id: UUID
    ) -> List[FileKeyShare]:
        """List file key shares"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT * FROM file_key_shares
                    WHERE file_id = $1
                    ORDER BY created_at DESC
                    """,
                    file_id
                )
                return [FileKeyShare(**dict(row)) for row in rows]
        except Exception as e:
            logger.error(f"Failed to list file key shares: {str(e)}")
            raise

    async def update_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID,
        update: FileKeyShareUpdate
    ) -> Optional[FileKeyShare]:
        """Update file key share"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    UPDATE file_key_shares
                    SET encrypted_key = COALESCE($3, encrypted_key)
                    WHERE file_id = $1 AND user_id = $2
                    RETURNING *
                    """,
                    file_id,
                    user_id,
                    update.encrypted_key
                )
                return FileKeyShare(**dict(row)) if row else None
        except Exception as e:
            logger.error(f"Failed to update file key share: {str(e)}")
            raise

    async def delete_file_key_share(
        self,
        file_id: UUID,
        user_id: UUID
    ) -> bool:
        """Delete file key share"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM file_key_shares
                    WHERE file_id = $1 AND user_id = $2
                    """,
                    file_id,
                    user_id
                )
                return result == "DELETE 1"
        except Exception as e:
            logger.error(f"Failed to delete file key share: {str(e)}")
            raise

    async def delete_all_file_key_shares(self, file_id: UUID) -> int:
        """Delete all file key shares for a file"""
        try:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    """
                    DELETE FROM file_key_shares
                    WHERE file_id = $1
                    """,
                    file_id
                )
                return int(result.split()[1])
        except Exception as e:
            logger.error(f"Failed to delete file key shares: {str(e)}")
            raise
