"""Job distribution service."""

import logging
from datetime import datetime
from typing import Optional, List
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    QUEUE_SIZE,
    QUEUE_WAIT_TIME,
    WORKER_COUNT,
    track_queue_metrics
)

class JobDistributionService:
    """Service for distributing jobs to workers."""

    def __init__(self, settings):
        """Initialize job distribution service."""
        self.settings = settings
        self.initialized = False

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize job distribution settings
            self.poll_interval = float(self.settings.get('poll_interval', 5.0))
            self.batch_size = int(self.settings.get('batch_size', 10))
            self.retry_limit = int(self.settings.get('retry_limit', 3))

            self.initialized = True
            log_info("Job distribution service initialized")

        except Exception as e:
            log_error(f"Failed to initialize job distribution service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Job distribution service cleaned up")

        except Exception as e:
            log_error(f"Error during job distribution service cleanup: {str(e)}")
            raise

    async def get_available_jobs(self, worker_id: str, limit: int = 10) -> List[dict]:
        """Get available jobs for a worker."""
        try:
            # Track queue metrics
            queue_size = await self._get_queue_size()
            QUEUE_SIZE.set(queue_size)
            WORKER_COUNT.inc()

            # Get jobs
            jobs = await self._fetch_jobs(limit)
            
            # Track wait time for jobs
            for job in jobs:
                created_at = datetime.fromisoformat(job['created_at'])
                wait_time = (datetime.utcnow() - created_at).total_seconds()
                QUEUE_WAIT_TIME.observe(wait_time)
                track_queue_metrics(wait_time, len(jobs))

            log_info(f"Retrieved {len(jobs)} jobs for worker {worker_id}")
            return jobs

        except Exception as e:
            log_error(f"Error getting available jobs: {str(e)}")
            raise

    async def assign_job(self, job_id: str, worker_id: str) -> bool:
        """Assign a job to a worker."""
        try:
            # Attempt to assign job
            assigned = await self._try_assign_job(job_id, worker_id)
            
            if assigned:
                log_info(f"Job {job_id} assigned to worker {worker_id}")
            else:
                log_warning(f"Failed to assign job {job_id} to worker {worker_id}")
            
            return assigned

        except Exception as e:
            log_error(f"Error assigning job {job_id} to worker {worker_id}: {str(e)}")
            raise

    async def release_job(self, job_id: str, worker_id: str):
        """Release a job from a worker."""
        try:
            await self._release_job(job_id, worker_id)
            log_info(f"Job {job_id} released from worker {worker_id}")

        except Exception as e:
            log_error(f"Error releasing job {job_id} from worker {worker_id}: {str(e)}")
            raise

    async def _get_queue_size(self) -> int:
        """Get current queue size."""
        # Implementation would query database for pending jobs
        return 0

    async def _fetch_jobs(self, limit: int) -> List[dict]:
        """Fetch available jobs from queue."""
        # Implementation would fetch jobs from database
        return []

    async def _try_assign_job(self, job_id: str, worker_id: str) -> bool:
        """Try to assign a job to a worker."""
        # Implementation would update job assignment in database
        return True

    async def _release_job(self, job_id: str, worker_id: str):
        """Release a job assignment."""
        # Implementation would update job status in database
        pass
