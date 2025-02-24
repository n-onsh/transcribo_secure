import os
import logging
from typing import Optional, List, Dict
import asyncpg
from datetime import datetime, timedelta
import uuid
import json
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

        # Job notification listeners
        self.job_listeners: Dict[str, asyncpg.Connection] = {}

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

    async def subscribe_to_job_updates(self, worker_id: str, callback) -> None:
        """Subscribe to job update notifications"""
        try:
            # Create dedicated connection for LISTEN
            conn = await asyncpg.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )

            # Set up notification handler
            async def handle_notification(conn, pid, channel, payload):
                try:
                    data = json.loads(payload)
                    await callback(data)
                except Exception as e:
                    logger.error(f"Error handling job notification: {str(e)}")

            # Start listening
            await conn.add_listener('job_updates', handle_notification)
            self.job_listeners[worker_id] = conn

            logger.info(f"Worker {worker_id} subscribed to job updates")

        except Exception as e:
            logger.error(f"Failed to subscribe to job updates: {str(e)}")
            raise

    async def unsubscribe_from_job_updates(self, worker_id: str) -> None:
        """Unsubscribe from job update notifications"""
        try:
            conn = self.job_listeners.pop(worker_id, None)
            if conn:
                await conn.close()
                logger.info(f"Worker {worker_id} unsubscribed from job updates")

        except Exception as e:
            logger.error(f"Failed to unsubscribe from job updates: {str(e)}")
            raise

    @track_time(DB_OPERATION_DURATION, {"operation": "claim_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "claim_job", "error_type": "unknown"})
    async def claim_job(self, worker_id: str) -> Optional[Job]:
        """Claim next available job using SELECT FOR UPDATE SKIP LOCKED"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Get next available job
                    row = await conn.fetchrow("""
                        SELECT *
                        FROM jobs
                        WHERE status = 'pending'
                        AND (next_retry_at IS NULL OR next_retry_at <= NOW())
                        ORDER BY priority DESC, created_at ASC
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    """)

                    if not row:
                        return None

                    # Update job with worker info
                    job_id = row['id']
                    await conn.execute("""
                        UPDATE jobs
                        SET locked_by = $1,
                            locked_at = NOW(),
                            status = 'processing'
                        WHERE id = $2
                    """, worker_id, job_id)

                    # Notify about job update
                    await conn.execute(
                        "SELECT pg_notify($1, $2)",
                        'job_updates',
                        json.dumps({
                            'job_id': str(job_id),
                            'status': 'processing',
                            'worker_id': worker_id
                        })
                    )

                    # Return claimed job
                    return Job.parse_obj(dict(row))

        except Exception as e:
            logger.error(f"Failed to claim job: {str(e)}")
            raise

    @track_time(DB_OPERATION_DURATION, {"operation": "release_stale_jobs"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "release_stale_jobs", "error_type": "unknown"})
    async def release_stale_jobs(self, max_lock_duration_minutes: int = 30) -> int:
        """Release jobs with stale locks"""
        try:
            async with self.pool.acquire() as conn:
                # Update stale jobs
                result = await conn.execute("""
                    WITH updated_jobs AS (
                        UPDATE jobs
                        SET 
                            status = 'pending',
                            locked_by = NULL,
                            locked_at = NULL,
                            retry_count = LEAST(retry_count + 1, max_retries),
                            next_retry_at = CASE 
                                WHEN retry_count < max_retries THEN NOW() + (INTERVAL '1 minute' * POWER(2, retry_count))
                                ELSE NULL
                            END
                        WHERE 
                            status = 'processing'
                            AND locked_by IS NOT NULL
                            AND locked_at < NOW() - ($1 * INTERVAL '1 minute')
                        RETURNING id
                    )
                    SELECT COUNT(*) FROM updated_jobs
                """, max_lock_duration_minutes)

                count = int(result.split()[1])
                if count > 0:
                    logger.info(f"Released {count} stale jobs")
                return count

        except Exception as e:
            logger.error(f"Failed to release stale jobs: {str(e)}")
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

    @track_time(DB_OPERATION_DURATION, {"operation": "get_jobs_by_user"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_jobs_by_user", "error_type": "unknown"})
    async def get_jobs_by_user(
        self,
        user_id: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Job]:
        """Get jobs for a user with optional status filter"""
        try:
            async with self.pool.acquire() as conn:
                # Build query
                query = """
                    SELECT *
                    FROM jobs
                    WHERE user_id = $1
                """
                params = [user_id]

                # Add status filter if provided
                if status:
                    query += " AND status = $2"
                    params.append(status)

                # Add limit and offset
                query += """
                    ORDER BY created_at DESC
                    LIMIT $%d
                    OFFSET $%d
                """ % (len(params) + 1, len(params) + 2)
                params.extend([limit, offset])

                # Execute query
                rows = await conn.fetch(query, *params)
                return [Job.parse_obj(dict(row)) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get jobs for user {user_id}: {str(e)}")
            raise

    @track_time(DB_OPERATION_DURATION, {"operation": "get_job_stats"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_job_stats", "error_type": "unknown"})
    async def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics by status"""
        try:
            async with self.pool.acquire() as conn:
                # Get counts for each status
                rows = await conn.fetch("""
                    SELECT status, COUNT(*) as count
                    FROM jobs
                    GROUP BY status
                """)
                
                # Convert to dictionary
                stats = {
                    row['status']: row['count']
                    for row in rows
                }
                
                # Ensure all statuses have a count
                for status in JobStatus:
                    if status not in stats:
                        stats[status] = 0
                        
                return stats

        except Exception as e:
            logger.error(f"Failed to get job stats: {str(e)}")
            raise

    async def close(self):
        """Close database connections"""
        try:
            # Close notification listeners
            for worker_id, conn in self.job_listeners.items():
                try:
                    await conn.close()
                except Exception as e:
                    logger.error(f"Error closing listener for worker {worker_id}: {str(e)}")

            # Close connection pool
            if self.pool:
                await self.pool.close()

            logger.info("Database connections closed")

        except Exception as e:
            logger.error(f"Error closing database connections: {str(e)}")
            raise
