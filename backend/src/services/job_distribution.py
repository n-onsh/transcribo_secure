"""Job distribution service for transcriber workers."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from opentelemetry import trace, logs
from opentelemetry.logs import Severity

from ..models.job import Job, JobStatus, JobPriority
from ..services.database import DatabaseService
from ..services.interfaces import StorageInterface
from ..utils.metrics import (
    WORKER_JOBS_ACTIVE,
    WORKER_JOBS_COMPLETED,
    WORKER_JOBS_FAILED,
    WORKER_LOAD_PERCENT,
    track_time,
    track_errors,
    update_gauge
)

logger = logs.get_logger(__name__)
tracer = trace.get_tracer(__name__)

class JobDistributor:
    """Manages job distribution across transcriber workers."""
    
    def __init__(
        self,
        db: DatabaseService,
        storage: StorageInterface,
        max_jobs_per_worker: int = 2,
        max_retries: int = 3,
        retry_delay: int = 60,  # seconds
        stale_job_timeout: int = 1800  # 30 minutes
    ):
        self.db = db
        self.storage = storage
        self.max_jobs_per_worker = max_jobs_per_worker
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.stale_job_timeout = stale_job_timeout
        self.worker_loads: Dict[str, float] = {}
        self.worker_jobs: Dict[str, List[UUID]] = {}

    async def initialize(self):
        """Initialize job distributor."""
        # Start background tasks
        asyncio.create_task(self._monitor_worker_loads())
        asyncio.create_task(self._cleanup_stale_jobs())
        logger.emit(
            "Job distributor initialized",
            severity=Severity.INFO
        )

    async def register_worker(self, worker_id: str) -> None:
        """Register a new worker."""
        self.worker_loads[worker_id] = 0.0
        self.worker_jobs[worker_id] = []
        logger.emit(
            "Worker registered",
            severity=Severity.INFO,
            attributes={"worker_id": worker_id}
        )

    async def unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker."""
        if worker_id in self.worker_loads:
            del self.worker_loads[worker_id]
        if worker_id in self.worker_jobs:
            # Release any claimed jobs
            for job_id in self.worker_jobs[worker_id]:
                await self._release_job(job_id)
            del self.worker_jobs[worker_id]
        logger.emit(
            "Worker unregistered",
            severity=Severity.INFO,
            attributes={"worker_id": worker_id}
        )

    @track_time("job_claim_duration", {"operation": "claim_job"})
    @track_errors("job_claim_errors", {"operation": "claim_job"})
    async def claim_job(self, worker_id: str) -> Optional[Job]:
        """Claim next available job for worker."""
        # Check worker capacity
        if len(self.worker_jobs.get(worker_id, [])) >= self.max_jobs_per_worker:
            return None

        # Get worker's current load
        worker_load = self.worker_loads.get(worker_id, 0.0)
        
        # Adjust job priority based on load
        priority_boost = 1.0 - (worker_load / 100.0)

        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Get next available job with load-adjusted priority
                job = await conn.fetchrow("""
                    SELECT j.*, jo.options
                    FROM jobs j
                    LEFT JOIN job_options jo ON j.id = jo.job_id
                    WHERE j.status = 'pending'
                    AND (j.next_retry_at IS NULL OR j.next_retry_at <= NOW())
                    ORDER BY 
                        j.priority * $1 DESC,
                        j.created_at ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                """, priority_boost)

                if not job:
                    return None

                # Update job status
                job_id = job['id']
                await conn.execute("""
                    UPDATE jobs
                    SET status = 'processing',
                        locked_by = $1,
                        locked_at = NOW(),
                        updated_at = NOW()
                    WHERE id = $2
                """, worker_id, job_id)

                # Track job
                self.worker_jobs[worker_id].append(job_id)
                update_gauge(WORKER_JOBS_ACTIVE, len(self.worker_jobs[worker_id]))

                logger.emit(
                    "Job claimed",
                    severity=Severity.INFO,
                    attributes={
                        "job_id": str(job_id),
                        "worker_id": worker_id,
                        "priority_boost": priority_boost
                    }
                )

                return Job.parse_obj(job)

    @track_time("job_complete_duration", {"operation": "complete_job"})
    @track_errors("job_complete_errors", {"operation": "complete_job"})
    async def complete_job(
        self,
        job_id: UUID,
        worker_id: str,
        status: JobStatus,
        error: Optional[str] = None
    ) -> None:
        """Mark job as completed or failed."""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Update job status
                await conn.execute("""
                    UPDATE jobs
                    SET status = $1,
                        error = $2,
                        completed_at = CASE WHEN $1 = 'completed' THEN NOW() ELSE NULL END,
                        updated_at = NOW(),
                        locked_by = NULL,
                        locked_at = NULL
                    WHERE id = $3
                """, status.value, error, job_id)

                # Update metrics
                if status == JobStatus.COMPLETED:
                    WORKER_JOBS_COMPLETED.inc()
                else:
                    WORKER_JOBS_FAILED.inc()

                # Remove from worker tracking
                if job_id in self.worker_jobs.get(worker_id, []):
                    self.worker_jobs[worker_id].remove(job_id)
                    update_gauge(WORKER_JOBS_ACTIVE, len(self.worker_jobs[worker_id]))

                logger.emit(
                    "Job completed",
                    severity=Severity.INFO,
                    attributes={
                        "job_id": str(job_id),
                        "worker_id": worker_id,
                        "status": status.value,
                        "error": error
                    }
                )

    async def _release_job(self, job_id: UUID) -> None:
        """Release a job back to the queue."""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                # Get current job state
                job = await conn.fetchrow("""
                    SELECT status, retry_count, max_retries
                    FROM jobs
                    WHERE id = $1
                    FOR UPDATE
                """, job_id)

                if not job:
                    return

                # Calculate next retry
                retry_count = job['retry_count'] + 1
                if retry_count > job['max_retries']:
                    # Mark as failed if max retries exceeded
                    await conn.execute("""
                        UPDATE jobs
                        SET status = 'failed',
                            error = 'Max retries exceeded',
                            updated_at = NOW(),
                            locked_by = NULL,
                            locked_at = NULL
                        WHERE id = $1
                    """, job_id)
                    WORKER_JOBS_FAILED.inc()
                else:
                    # Calculate exponential backoff
                    next_retry = datetime.utcnow() + timedelta(
                        seconds=self.retry_delay * (2 ** (retry_count - 1))
                    )
                    
                    # Release for retry
                    await conn.execute("""
                        UPDATE jobs
                        SET status = 'pending',
                            retry_count = $1,
                            next_retry_at = $2,
                            updated_at = NOW(),
                            locked_by = NULL,
                            locked_at = NULL
                        WHERE id = $3
                    """, retry_count, next_retry, job_id)

                logger.emit(
                    "Job released",
                    severity=Severity.INFO,
                    attributes={
                        "job_id": str(job_id),
                        "retry_count": retry_count,
                        "max_retries": job['max_retries']
                    }
                )

    async def _monitor_worker_loads(self):
        """Monitor worker load metrics."""
        while True:
            try:
                for worker_id, jobs in self.worker_jobs.items():
                    # Calculate load based on active jobs
                    load = (len(jobs) / self.max_jobs_per_worker) * 100
                    self.worker_loads[worker_id] = load
                    update_gauge(
                        WORKER_LOAD_PERCENT,
                        load,
                        {"worker_id": worker_id}
                    )
            except Exception as e:
                logger.emit(
                    "Error monitoring worker loads",
                    severity=Severity.ERROR,
                    attributes={"error": str(e)}
                )
            await asyncio.sleep(60)  # Update every minute

    async def _cleanup_stale_jobs(self):
        """Clean up stale jobs."""
        while True:
            try:
                # Find stale jobs
                stale_time = datetime.utcnow() - timedelta(
                    seconds=self.stale_job_timeout
                )
                async with self.db.pool.acquire() as conn:
                    stale_jobs = await conn.fetch("""
                        SELECT id, locked_by
                        FROM jobs
                        WHERE status = 'processing'
                        AND locked_at < $1
                    """, stale_time)

                    # Release each stale job
                    for job in stale_jobs:
                        await self._release_job(job['id'])
                        
                        # Update worker tracking
                        worker_id = job['locked_by']
                        if worker_id and job['id'] in self.worker_jobs.get(worker_id, []):
                            self.worker_jobs[worker_id].remove(job['id'])

                    if stale_jobs:
                        logger.emit(
                            "Cleaned up stale jobs",
                            severity=Severity.INFO,
                            attributes={"count": len(stale_jobs)}
                        )

            except Exception as e:
                logger.emit(
                    "Error cleaning up stale jobs",
                    severity=Severity.ERROR,
                    attributes={"error": str(e)}
                )
            await asyncio.sleep(300)  # Run every 5 minutes
