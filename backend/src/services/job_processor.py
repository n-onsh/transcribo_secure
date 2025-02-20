from datetime import datetime
from uuid import uuid4
import logging
from typing import Optional
from ..models.job import Job, JobStatus, JobType, JobUpdate
from .database import DatabaseService
from .storage import StorageService

logger = logging.getLogger(__name__)

class JobProcessor:
    def __init__(self, db: DatabaseService, storage: StorageService):
        self.db = db
        self.storage = storage

    async def create_transcription_job(
        self,
        file_id: uuid4,
        user_id: str,
        file_name: str,
        metadata: Optional[dict] = None
    ) -> Job:
        """Create a new transcription job"""
        try:
            # Create job metadata
            job_metadata = metadata or {}
            job_metadata.update({
                "original_filename": file_name,
                "created_at": datetime.utcnow().isoformat()
            })

            # Create job
            job = Job(
                job_id=uuid4(),
                file_id=file_id,
                user_id=user_id,
                job_type=JobType.TRANSCRIPTION,
                status=JobStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                metadata=job_metadata
            )

            # Save to database
            created_job = await self.db.create_job(job)
            logger.info(f"Created transcription job {created_job.job_id}")
            return created_job

        except Exception as e:
            logger.error(f"Error creating transcription job: {str(e)}")
            raise

    async def process_job_result(
        self,
        job_id: uuid4,
        results: dict,
        result_type: str = "transcription"
    ) -> Job:
        """Process and store job results"""
        try:
            # Get job
            job = await self.db.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")

            # Store results
            result_file_name = f"{job_id}_{result_type}_results.json"
            await self.storage.store_file(
                file_id=job.file_id,
                file_data=results,
                file_name=result_file_name,
                file_type="output"
            )

            # Update job
            job_update = JobUpdate(
                status=JobStatus.COMPLETED,
                metadata={
                    **job.metadata,
                    "result_file": result_file_name,
                    "completed_at": datetime.utcnow().isoformat()
                }
            )
            updated_job = await self.db.update_job(job_id, job_update)
            
            logger.info(f"Processed results for job {job_id}")
            return updated_job

        except Exception as e:
            logger.error(f"Error processing job results: {str(e)}")
            # Update job as failed
            await self.db.update_job(
                job_id,
                JobUpdate(
                    status=JobStatus.FAILED,
                    error_message=str(e)
                )
            )
            raise

    async def handle_job_failure(
        self,
        job_id: uuid4,
        error: Exception
    ) -> Job:
        """Handle job failure"""
        try:
            # Update job status
            job_update = JobUpdate(
                status=JobStatus.FAILED,
                error_message=str(error),
                metadata={"failed_at": datetime.utcnow().isoformat()}
            )
            updated_job = await self.db.update_job(job_id, job_update)
            
            logger.error(f"Job {job_id} failed: {str(error)}")
            return updated_job

        except Exception as e:
            logger.error(f"Error handling job failure: {str(e)}")
            raise

    async def cleanup_old_jobs(self, days: int = 7):
        """Cleanup old completed/failed jobs"""
        try:
            await self.db.cleanup_old_jobs(days)
            logger.info(f"Cleaned up jobs older than {days} days")
        except Exception as e:
            logger.error(f"Error cleaning up old jobs: {str(e)}")
            raise