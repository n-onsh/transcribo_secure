import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
import json
import uuid
import httpx
from .database import DatabaseService
from .storage import StorageService
from ..models.job import Job, JobStatus, JobPriority, JobFilter, JobUpdate, Transcription
from ..utils.exceptions import (
    ResourceNotFoundError,
    ResourceConflictError,
    TranscriptionError
)
from ..utils.metrics import (
    JOBS_TOTAL,
    JOB_PROCESSING_DURATION,
    JOB_QUEUE_SIZE,
    JOB_RETRY_COUNT,
    track_time,
    track_errors,
    update_gauge,
    increment_counter
)

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, storage: Optional[StorageService] = None, db: Optional[DatabaseService] = None):
        """Initialize job manager"""
        self.db = db or DatabaseService()
        self.storage = storage or StorageService()
        
        # Transcriber service URL
        self.transcriber_url = os.getenv("TRANSCRIBER_URL", "http://transcriber:8000")
        
        # Worker settings
        self.worker_id = str(uuid.uuid4())
        self.max_concurrent_jobs = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
        self.job_timeout = int(os.getenv("JOB_TIMEOUT_MINUTES", "120"))
        self.cleanup_days = int(os.getenv("JOB_CLEANUP_DAYS", "30"))
        self.max_retries = int(os.getenv("MAX_JOB_RETRIES", "3"))
        
        # Background tasks
        self.worker_tasks: List[asyncio.Task] = []
        self.cleanup_task: Optional[asyncio.Task] = None
        self.health_check_task: Optional[asyncio.Task] = None
        
        # Active jobs
        self.active_jobs: Dict[str, Job] = {}
        
        logger.info(f"Job manager initialized with worker ID {self.worker_id}")

    async def start(self):
        """Start background tasks"""
        try:
            # Initialize services
            await self.db.initialize_database()
            
            # Subscribe to job updates
            await self.db.subscribe_to_job_updates(self.worker_id, self._handle_job_update)
            
            # Start worker tasks
            for _ in range(self.max_concurrent_jobs):
                task = asyncio.create_task(self._job_worker())
                self.worker_tasks.append(task)
            
            # Start cleanup and health check tasks
            self.cleanup_task = asyncio.create_task(self._cleanup_old_jobs())
            self.health_check_task = asyncio.create_task(self._health_check())
            
            logger.info(f"Job manager started with {self.max_concurrent_jobs} workers")
            
        except Exception as e:
            logger.error(f"Failed to start job manager: {str(e)}")
            raise

    async def stop(self):
        """Stop background tasks"""
        try:
            # Cancel all tasks
            for task in self.worker_tasks:
                task.cancel()
            if self.cleanup_task:
                self.cleanup_task.cancel()
            if self.health_check_task:
                self.health_check_task.cancel()
            
            # Wait for tasks to complete
            await asyncio.gather(
                *self.worker_tasks,
                self.cleanup_task,
                self.health_check_task,
                return_exceptions=True
            )
            
            # Unsubscribe from job updates
            await self.db.unsubscribe_from_job_updates(self.worker_id)
            
            # Close services
            await self.db.close()
            
            logger.info("Job manager stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop job manager: {str(e)}")
            raise

    @track_time(JOB_PROCESSING_DURATION, {"operation": "create"})
    async def create_job(
        self,
        user_id: str,
        file_data: bytes,
        file_name: str,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: Optional[int] = None
    ) -> Job:
        """Create a new transcription job"""
        try:
            # Create job record
            job = Job(
                user_id=user_id,
                file_name=file_name,
                file_size=len(file_data),
                priority=priority,
                max_retries=max_retries or self.max_retries
            )
            
            # Store file
            await self.storage.store_file(
                user_id,
                file_data,
                file_name,
                "audio"
            )
            
            # Save job
            job = await self.db.create_job(job)
            
            # Update metrics
            increment_counter(JOBS_TOTAL, {"status": job.status})
            update_gauge(JOB_QUEUE_SIZE, 1, {"priority": job.priority.name})
            
            logger.info(f"Created job {job.id} for user {user_id}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to create job: {str(e)}")
            raise

    @track_time(JOB_PROCESSING_DURATION, {"operation": "get"})
    async def get_job(self, job_id: str, user_id: Optional[str] = None) -> Optional[Job]:
        """Get job by ID with optional user verification"""
        try:
            job = await self.db.get_job(job_id)
            if not job:
                raise ResourceNotFoundError("job", job_id)
                
            # Verify ownership
            if user_id and job.user_id != user_id:
                raise AuthorizationError("Access denied")
                
            return job
            
        except Exception as e:
            logger.error(f"Failed to get job: {str(e)}")
            raise

    async def list_jobs(
        self,
        user_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Job]:
        """List jobs with filtering"""
        try:
            filter = JobFilter(user_id=user_id, status=status)
            return await self.db.list_jobs(
                filter=filter,
                limit=limit,
                offset=offset
            )
        except Exception as e:
            logger.error(f"Failed to list jobs: {str(e)}")
            raise

    @track_time(JOB_PROCESSING_DURATION, {"operation": "update"})
    async def update_job(self, job_id: str, update: JobUpdate, user_id: Optional[str] = None) -> Job:
        """Update job with optional user verification"""
        try:
            # Get job
            job = await self.get_job(job_id, user_id)
            
            # Track old status for metrics
            old_status = job.status
            old_priority = job.priority
            
            # Apply update
            update.apply_to(job)
            
            # Save changes
            job = await self.db.update_job(job)
            
            # Update metrics if status changed
            if job.status != old_status:
                increment_counter(JOBS_TOTAL, {"status": job.status})
                
            # Update queue size if priority changed
            if job.priority != old_priority:
                update_gauge(JOB_QUEUE_SIZE, -1, {"priority": old_priority.name})
                update_gauge(JOB_QUEUE_SIZE, 1, {"priority": job.priority.name})
            
            return job
            
        except Exception as e:
            logger.error(f"Failed to update job: {str(e)}")
            raise

    async def delete_job(self, job_id: str, user_id: Optional[str] = None):
        """Delete job with optional user verification"""
        try:
            # Get job
            job = await self.get_job(job_id, user_id)
            if not job:
                return
            
            # Delete from storage
            await self.storage.delete_file(job.user_id, job.file_name, "audio")
            await self.storage.delete_file(job.user_id, f"{job.id}.json", "transcription")
            
            # Delete from database
            await self.db.delete_job(job_id)
            
            logger.info(f"Deleted job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete job: {str(e)}")
            raise

    async def get_transcription(self, job_id: str, user_id: Optional[str] = None) -> Transcription:
        """Get job transcription with optional user verification"""
        try:
            # Get job
            job = await self.get_job(job_id, user_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            # Get transcription
            transcription_data = await self.storage.retrieve_file(
                job.user_id,
                f"{job.id}.json",
                "transcription"
            )
            
            return Transcription.parse_raw(transcription_data)
            
        except Exception as e:
            logger.error(f"Failed to get transcription: {str(e)}")
            raise

    async def cancel_job(self, job_id: str, user_id: Optional[str] = None) -> Job:
        """Cancel a job"""
        try:
            # Get job
            job = await self.get_job(job_id, user_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            # Check if job can be cancelled
            if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot cancel job in {job.status} status"
                )
            
            # Update job status
            job.cancel()
            await self.db.update_job(job)
            
            logger.info(f"Cancelled job {job.id}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to cancel job: {str(e)}")
            raise

    async def retry_job(self, job_id: str, user_id: Optional[str] = None) -> Job:
        """Retry a failed job"""
        try:
            # Get job
            job = await self.get_job(job_id, user_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            # Check if job can be retried
            if not job.can_retry():
                raise HTTPException(
                    status_code=400,
                    detail="Job cannot be retried"
                )
            
            # Reset job status
            job.status = JobStatus.PENDING
            job.error = None
            job.progress = 0.0
            job.updated_at = datetime.utcnow()
            
            # Save changes
            await self.db.update_job(job)
            
            logger.info(f"Retrying job {job.id}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to retry job: {str(e)}")
            raise

    async def _handle_job_update(self, data: Dict):
        """Handle job update notification"""
        try:
            job_id = data.get('job_id')
            status = data.get('status')
            worker_id = data.get('worker_id')
            
            if job_id in self.active_jobs and worker_id != self.worker_id:
                logger.warning(f"Job {job_id} taken by worker {worker_id}")
                self.active_jobs.pop(job_id, None)
                
        except Exception as e:
            logger.error(f"Error handling job update: {str(e)}")

    @track_time(JOB_PROCESSING_DURATION, {"operation": "process"})
    async def _process_job(self, job: Job):
        """Process a single job"""
        start_time = time.time()
        try:
            # Add to active jobs
            self.active_jobs[job.id] = job
            
            # Get audio file
            audio_data = await self.storage.retrieve_file(
                job.user_id,
                job.file_name,
                "audio"
            )
            
            # Submit job to transcriber service
            async with httpx.AsyncClient() as client:
                # Upload audio file to transcriber
                response = await client.post(
                    f"{self.transcriber_url}/transcribe",
                    files={"audio": audio_data},
                    params={"job_id": job.id}
                )
                response.raise_for_status()
                
                # Get transcription result
                transcription = response.json()
                
                # Store transcription
                await self.storage.store_file(
                    job.user_id,
                    json.dumps(transcription).encode(),
                    f"{job.id}.json",
                    "transcription"
                )
            
            # Mark complete
            job.complete()
            await self.db.update_job(job)
            
            # Update metrics
            increment_counter(JOBS_TOTAL, {"status": job.status})
            JOB_PROCESSING_DURATION.labels(status="completed").observe(
                time.time() - start_time
            )
            
            logger.info(f"Completed job {job.id}")
            
        except asyncio.CancelledError:
            # Handle cancellation
            job.cancel()
            await self.db.update_job(job)
            
            # Update metrics
            increment_counter(JOBS_TOTAL, {"status": job.status})
            JOB_PROCESSING_DURATION.labels(status="cancelled").observe(
                time.time() - start_time
            )
            raise
            
        except Exception as e:
            logger.error(f"Failed to process job {job.id}: {str(e)}")
            job.fail(str(e))
            await self.db.update_job(job)
            
            # Update metrics
            increment_counter(JOBS_TOTAL, {"status": job.status})
            increment_counter(JOB_RETRY_COUNT, {"status": "failed"})
            JOB_PROCESSING_DURATION.labels(status="failed").observe(
                time.time() - start_time
            )
            
        finally:
            # Remove from active jobs
            self.active_jobs.pop(job.id, None)

    async def _job_worker(self):
        """Worker task to process jobs"""
        while True:
            try:
                # Try to claim a job
                job = await self.db.claim_job(self.worker_id)
                if job:
                    try:
                        # Process job
                        await self._process_job(job)
                    except Exception as e:
                        logger.error(f"Error processing job {job.id}: {str(e)}")
                else:
                    # No jobs available, wait before trying again
                    await asyncio.sleep(5)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in job worker: {str(e)}")
                await asyncio.sleep(1)

    async def _cleanup_old_jobs(self):
        """Background task to clean up old jobs"""
        while True:
            try:
                # Delete old jobs
                await self.db.cleanup_old_jobs(self.cleanup_days)
                
                # Sleep for a day
                await asyncio.sleep(24 * 60 * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {str(e)}")
                await asyncio.sleep(60 * 60)

    async def _health_check(self):
        """Background task to check worker health"""
        while True:
            try:
                # Release stale jobs
                await self.db.release_stale_jobs(self.job_timeout)
                
                # Sleep for a minute
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {str(e)}")
                await asyncio.sleep(10)

    async def _update_progress(self, job_id: str, progress: float):
        """Update job progress"""
        try:
            update = JobUpdate(progress=progress)
            await self.update_job(job_id, update)
        except Exception as e:
            logger.error(f"Failed to update job progress: {str(e)}")
