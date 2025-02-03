import asyncio
import pytest
import uuid
from datetime import datetime
from backend_api.src.models.job import Job, JobStatus, JobType, JobUpdate
from backend_api.src.services.job_manager import JobManager

# A fake database service that stores jobs in a dictionary.
class FakeDatabaseService:
    def __init__(self):
        self.jobs = {}

    async def create_job(self, job: Job):
        self.jobs[job.job_id] = job
        return job

    async def get_job(self, job_id: uuid.UUID):
        return self.jobs.get(job_id)

    async def update_job(self, job_id: uuid.UUID, update: JobUpdate):
        job = self.jobs.get(job_id)
        if job:
            if update.status:
                job.status = update.status
            if update.error_message is not None:
                job.error_message = update.error_message
            if update.progress is not None:
                job.progress = update.progress
            job.updated_at = datetime.utcnow()
            self.jobs[job_id] = job
            return job
        return None

    async def get_pending_jobs(self, limit: int = 1):
        pending = [job for job in self.jobs.values() if job.status == JobStatus.PENDING]
        return pending[:limit]

    async def close(self):
        pass

@pytest.fixture
def fake_db_service():
    return FakeDatabaseService()

@pytest.fixture
def job_manager(fake_db_service):
    manager = JobManager(fake_db_service)
    return manager

@pytest.mark.asyncio
async def test_create_and_update_job(job_manager):
    file_id = uuid.uuid4()
    user_id = "test_user"
    
    # Create a transcription job.
    job = await job_manager.create_transcription_job(file_id=file_id, user_id=user_id, metadata={"key": "value"})
    assert job.job_type == JobType.TRANSCRIPTION
    assert job.status == JobStatus.PENDING

    # Update the job to PROCESSING.
    update = JobUpdate(status=JobStatus.PROCESSING)
    updated_job = await job_manager.update_job(job.job_id, update)
    assert updated_job.status == JobStatus.PROCESSING

    # Finally, update the job to COMPLETED with full progress.
    update = JobUpdate(status=JobStatus.COMPLETED, progress=100.0)
    updated_job = await job_manager.update_job(job.job_id, update)
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.progress == 100.0
