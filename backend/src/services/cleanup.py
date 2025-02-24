from datetime import datetime, timedelta
import asyncio
from typing import Optional
from uuid import UUID
import logging
from .database import DatabaseService
from .storage import StorageService
from ..models.job import Job, JobStatus
from ..config import get_settings

logger = logging.getLogger(__name__)

class CleanupService:
    def __init__(self, db: DatabaseService, storage: StorageService):
        self.db = db
        self.storage = storage
        self.settings = get_settings()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.retention_days = 7

    async def start(self):
        """Start the cleanup service"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup service started")

    async def stop(self):
        """Stop the cleanup service"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Cleanup service stopped")

    async def _cleanup_loop(self):
        """Main cleanup loop"""
        while self.is_running:
            try:
                # Run cleanup
                await self._perform_cleanup()
                # Wait for next cleanup cycle (check every hour)
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {str(e)}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def _perform_cleanup(self):
        """Perform the cleanup operation"""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        try:
            # Get files older than retention period
            expired_files = await self._get_expired_files(cutoff_date)
            logger.info(f"Found {len(expired_files)} files to clean up")

            for file_id, file_name, file_type in expired_files:
                try:
                    # Delete from storage
                    await self.storage.delete_file(
                        file_id=file_id,
                        file_name=file_name,
                        file_type=file_type
                    )
                    
                    # Delete from database
                    await self._delete_file_data(file_id)
                    
                    logger.info(f"Cleaned up file {file_id}")
                    
                except Exception as e:
                    logger.error(f"Error cleaning up file {file_id}: {str(e)}")

            # Cleanup old job records
            await self._cleanup_old_jobs(cutoff_date)
            
        except Exception as e:
            logger.error(f"Error performing cleanup: {str(e)}")

    async def _get_expired_files(self, cutoff_date: datetime) -> list:
        """Get list of expired files"""
        async with self.db.pool.acquire() as conn:
            result = await conn.fetch("""
                SELECT file_id, file_name, file_type
                FROM files
                WHERE created_at < $1
                AND file_id NOT IN (
                    SELECT file_id 
                    FROM jobs 
                    WHERE status = 'processing'
                )
            """, cutoff_date)
            return [(row['file_id'], row['file_name'], row['file_type']) for row in result]

    async def _delete_file_data(self, file_id: UUID):
        """Delete file metadata from database"""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Delete associated jobs first
                await conn.execute("DELETE FROM jobs WHERE file_id = $1", file_id)
                # Then delete file record
                await conn.execute("DELETE FROM files WHERE file_id = $1", file_id)

    async def _cleanup_old_jobs(self, cutoff_date: datetime):
        """Clean up old completed/failed job records"""
        async with self.db.pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM jobs
                WHERE created_at < $1
                AND status IN ('completed', 'failed')
            """, cutoff_date)
            deleted_count = result.split()[-1]  # Get count from "DELETE X" message
            logger.info(f"Cleaned up {deleted_count} old job records")
