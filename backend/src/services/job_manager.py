from datetime import datetime
import asyncio
from uuid import uuid4
from typing import Optional
import httpx
from ..models.job import Job, JobStatus, JobType, JobUpdate
from ..services.database import DatabaseService
from ..config import get_settings
import logging

logger = logging.getLogger(__name__)

class JobManager:
    def __init__(self, db: DatabaseService):
        self.db = db
        self.settings = get_settings()
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the job manager"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._process_jobs())
        logger.info("Job manager started")

    async def stop(self):
        """Stop the job manager"""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Job manager stopped")

    async def create_transcription_job(
        self,
        file_id: uuid4,
        user_id: str,
        metadata: Optional[dict] = None
    ) -> Job:
        """Create a new transcription job"""
        job = Job(
            job_id=uuid4(),
            file_id=file_id,
            user_id=user_id,
            job_type=JobType.TRANSCRIPTION,
            status=JobStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        return await self.db.create_job(job)

    async def update_job(self, job_id: uuid4, update: JobUpdate) -> Optional[Job]:
        """Update job status and progress"""
        return await self.db.update_job(job_id, update)

    async def _process_jobs(self):
        """Main job processing loop"""
        while self.is_running:
            try:
                # Get pending jobs
                pending_jobs = await self.db.get_pending_jobs(limit=5)
                
                for job in pending_jobs:
                    try:
                        if job.job_type == JobType.TRANSCRIPTION:
                            await self._process_transcription_job(job)
                        # Add other job types here
                    except Exception as e:
                        logger.error(f"Error processing job {job.job_id}: {str(e)}")
                        await self.update_job(
                            job.job_id,
                            JobUpdate(
                                status=JobStatus.FAILED,
                                error_message=str(e)
                            )
                        )
                
                # Wait before next batch
                await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Error in job processing loop: {str(e)}")
                await asyncio.sleep(10)  # Longer wait on error

    async def _process_transcription_job(self, job: Job):
        """Process a transcription job"""
        # Update job status to processing
        await self.update_job(
            job.job_id,
            JobUpdate(status=JobStatus.PROCESSING)
        )
        
        try:
            # Make request to transcriber service
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.settings.TRANSCRIBER_URL}/transcribe",
                    json={
                        "job_id": str(job.job_id),
                        "file_id": str(job.file_id),
                        "metadata": job.metadata
                    },
                    timeout=30.0
                )
                
                if response.status_code != 202:  # Accepted
                    raise Exception(
                        f"Transcriber service returned status {response.status_code}"
                    )
                
                logger.info(f"Job {job.job_id} sent to transcriber service")
                
        except Exception as e:
            logger.error(f"Error sending job {job.job_id} to transcriber: {str(e)}")
            await self.update_job(
                job.job_id,
                JobUpdate(
                    status=JobStatus.FAILED,
                    error_message=f"Failed to send to transcriber: {str(e)}"
                )
            )