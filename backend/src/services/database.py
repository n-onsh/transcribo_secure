import os
from typing import Optional, List, Dict
from opentelemetry import trace
from ..utils.logging import log_info, log_error
import asyncpg
from datetime import datetime, timedelta
import uuid
import json
from ..models.user import User
from ..models.job import Job, JobStatus, JobFilter, TranscriptionOptions
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

        log_info("Database service initialized")

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

            log_info("Database initialized", {
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "pool_size": len(self.pool._holders)
            })

        except Exception as e:
            log_error("Failed to initialize database", {"error": str(e)})
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
                    log_error("Error handling job notification", {"error": str(e)})

            # Start listening
            await conn.add_listener('job_updates', handle_notification)
            self.job_listeners[worker_id] = conn

            log_info("Worker subscribed to job updates", {"worker_id": worker_id})

        except Exception as e:
            log_error("Failed to subscribe to job updates", {
                "error": str(e),
                "worker_id": worker_id
            })
            raise

    async def unsubscribe_from_job_updates(self, worker_id: str) -> None:
        """Unsubscribe from job update notifications"""
        try:
            conn = self.job_listeners.pop(worker_id, None)
            if conn:
                await conn.close()
                log_info("Worker unsubscribed from job updates", {"worker_id": worker_id})

        except Exception as e:
            log_error("Failed to unsubscribe from job updates", {
                "error": str(e),
                "worker_id": worker_id
            })
            raise

    @track_time(DB_OPERATION_DURATION, {"operation": "claim_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "claim_job", "error_type": "unknown"})
    async def claim_job(self, worker_id: str) -> Optional[Job]:
        """Claim next available job using SELECT FOR UPDATE SKIP LOCKED"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Get next available job with options
                    row = await conn.fetchrow("""
                        SELECT j.*, jo.options
                        FROM jobs j
                        LEFT JOIN job_options jo ON j.id = jo.job_id
                        WHERE j.status = 'pending'
                        AND (j.next_retry_at IS NULL OR j.next_retry_at <= NOW())
                        ORDER BY j.priority DESC, j.created_at ASC
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

                    # Parse job with options
                    job_dict = dict(row)
                    if 'options' in job_dict:
                        options_dict = job_dict.pop('options')
                        if options_dict:
                            job_dict['options'] = TranscriptionOptions.parse_obj(options_dict)
                    return Job.parse_obj(job_dict)

        except Exception as e:
            log_error("Failed to claim job", {
                "error": str(e),
                "worker_id": worker_id
            })
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
                    log_info("Released stale jobs", {
                        "count": count,
                        "max_lock_duration": max_lock_duration_minutes
                    })
                return count

        except Exception as e:
            log_error("Failed to release stale jobs", {
                "error": str(e),
                "max_lock_duration": max_lock_duration_minutes
            })
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

    async def estimate_processing_time(
        self,
        duration: float,
        language: str
    ) -> Dict[str, Any]:
        """Get processing time estimate from database"""
        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM estimate_processing_time($1, $2)
                """, duration, language)
                
                return {
                    "estimated_time": row["estimated_seconds"],
                    "range": (row["min_seconds"], row["max_seconds"]),
                    "confidence": row["confidence"]
                }
        except Exception as e:
            log_error("Failed to estimate processing time", {
                "error": str(e),
                "duration": duration,
                "language": language
            })
            # Return default estimate
            return {
                "estimated_time": duration * 2,
                "range": (duration, duration * 3),
                "confidence": 0.5
            }

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get job performance metrics by language"""
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM job_performance_metrics
                """)
                
                return {
                    row["language"]: {
                        "total_jobs": row["total_jobs"],
                        "avg_processing_time": row["avg_processing_time"],
                        "min_processing_time": row["min_processing_time"],
                        "max_processing_time": row["max_processing_time"],
                        "avg_word_count": row["avg_word_count"],
                        "seconds_per_word": row["seconds_per_word"]
                    }
                    for row in rows
                }
        except Exception as e:
            log_error("Failed to get performance metrics", {"error": str(e)})
            return {}

    async def create_job(self, job: Job) -> Job:
        """Create a new job with options and time estimates"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Get time estimate
                    if not job.estimated_time:
                        estimate = await self.estimate_processing_time(
                            job.duration or job.file_size / 16000,  # Rough duration estimate
                            job.options.language if job.options else "de"
                        )
                        job.estimated_time = estimate["estimated_time"]
                        job.estimated_range = estimate["range"]
                        job.estimate_confidence = estimate["confidence"]

                    # Insert job with time estimates
                    row = await conn.fetchrow("""
                        INSERT INTO jobs (
                            id, owner_id, file_name, file_size, status,
                            priority, max_retries, created_at, updated_at,
                            estimated_time, estimated_range_min, estimated_range_max,
                            estimate_confidence
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        RETURNING *
                    """, str(job.id), job.owner_id, job.file_name, job.file_size,
                        job.status.value, job.priority.value, job.max_retries,
                        job.created_at, job.updated_at,
                        job.estimated_time,
                        job.estimated_range[0] if job.estimated_range else None,
                        job.estimated_range[1] if job.estimated_range else None,
                        job.estimate_confidence)

                    # Insert job options
                    if job.options:
                        await conn.execute("""
                            INSERT INTO job_options (job_id, options)
                            VALUES ($1, $2)
                        """, str(job.id), json.dumps(job.options.dict()))

                    # Return created job with time estimates
                    job_dict = dict(row)
                    if job.options:
                        job_dict['options'] = job.options
                    if job_dict['estimated_range_min'] is not None and job_dict['estimated_range_max'] is not None:
                        job_dict['estimated_range'] = (job_dict.pop('estimated_range_min'), job_dict.pop('estimated_range_max'))
                    return Job.parse_obj(job_dict)

        except Exception as e:
            log_error("Failed to create job", {
                "error": str(e),
                "job_id": str(job.id)
            })
            raise

    async def update_job(self, job_id: str, job: Job) -> Optional[Job]:
        """Update job with time estimates"""
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Update job with time estimates
                    row = await conn.fetchrow("""
                        UPDATE jobs
                        SET status = $1,
                            progress = $2,
                            error = $3,
                            retry_count = $4,
                            next_retry_at = $5,
                            completed_at = $6,
                            cancelled_at = $7,
                            updated_at = $8,
                            estimated_time = $9,
                            estimated_range_min = $10,
                            estimated_range_max = $11,
                            estimate_confidence = $12
                        WHERE id = $13
                        RETURNING *
                    """, job.status.value, job.progress, job.error,
                        job.retry_count, job.next_retry_at, job.completed_at,
                        job.cancelled_at, job.updated_at,
                        job.estimated_time,
                        job.estimated_range[0] if job.estimated_range else None,
                        job.estimated_range[1] if job.estimated_range else None,
                        job.estimate_confidence,
                        job_id)

                    if not row:
                        return None

                    # Update job options if provided
                    if job.options:
                        await conn.execute("""
                            UPDATE job_options
                            SET options = $1
                            WHERE job_id = $2
                        """, json.dumps(job.options.dict()), job_id)

                    # Return updated job with time estimates
                    job_dict = dict(row)
                    if job.options:
                        job_dict['options'] = job.options
                    if job_dict['estimated_range_min'] is not None and job_dict['estimated_range_max'] is not None:
                        job_dict['estimated_range'] = (job_dict.pop('estimated_range_min'), job_dict.pop('estimated_range_max'))
                    return Job.parse_obj(job_dict)

        except Exception as e:
            log_error("Failed to update job", {
                "error": str(e),
                "job_id": job_id
            })
            raise

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
        offset: int = 0,
        language: Optional[str] = None
    ) -> List[Job]:
        """Get jobs for a user with optional filters"""
        try:
            async with self.pool.acquire() as conn:
                # Build query
                query = """
                    SELECT j.*, jo.options
                    FROM jobs j
                    LEFT JOIN job_options jo ON j.id = jo.job_id
                    WHERE j.owner_id = $1
                """
                params = [user_id]

                # Add status filter if provided
                if status:
                    query += " AND j.status = $2"
                    params.append(status)

                # Add language filter if provided
                if language:
                    query += " AND jo.options->>'language' = $%d" % (len(params) + 1)
                    params.append(language)

                # Add limit and offset
                query += """
                    ORDER BY j.created_at DESC
                    LIMIT $%d
                    OFFSET $%d
                """ % (len(params) + 1, len(params) + 2)
                params.extend([limit, offset])

                # Execute query
                rows = await conn.fetch(query, *params)
                
                # Parse jobs with options
                jobs = []
                for row in rows:
                    job_dict = dict(row)
                    if 'options' in job_dict:
                        options_dict = job_dict.pop('options')
                        if options_dict:
                            job_dict['options'] = TranscriptionOptions.parse_obj(options_dict)
                    jobs.append(Job.parse_obj(job_dict))
                return jobs

        except Exception as e:
            log_error("Failed to get jobs for user", {
                "error": str(e),
                "user_id": user_id,
                "status": status.value if status else None,
                "language": language
            })
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
            log_error("Failed to get job stats", {"error": str(e)})
            raise

    async def close(self):
        """Close database connections"""
        try:
            # Close notification listeners
            for worker_id, conn in self.job_listeners.items():
                try:
                    await conn.close()
                except Exception as e:
                    log_error("Error closing listener for worker", {
                        "error": str(e),
                        "worker_id": worker_id
                    })

            # Close connection pool
            if self.pool:
                await self.pool.close()

            log_info("Database connections closed")

        except Exception as e:
            log_error("Error closing database connections", {"error": str(e)})
            raise
