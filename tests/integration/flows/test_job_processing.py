import pytest
import uuid
import asyncio
from datetime import datetime, timedelta
from backend.src.models.job import Job, JobStatus, JobPriority
from backend.src.services.provider import ServiceProvider
from backend.src.services.interfaces import (
    DatabaseInterface,
    StorageInterface,
    JobManagerInterface
)

@pytest.fixture
async def service_provider():
    """Create and initialize service provider"""
    provider = ServiceProvider()
    await provider.initialize()
    yield provider
    await provider.cleanup()

@pytest.fixture
def db(service_provider):
    """Get database service"""
    return service_provider.get(DatabaseInterface)

@pytest.fixture
def storage(service_provider):
    """Get storage service"""
    return service_provider.get(StorageInterface)

@pytest.fixture
def job_manager(service_provider):
    """Get job manager service"""
    return service_provider.get(JobManagerInterface)

@pytest.fixture
async def test_job(job_manager):
    """Create a test job"""
    job = await job_manager.create_job(
        user_id=str(uuid.uuid4()),
        file_data=b"test audio data",
        file_name="test.mp3",
        priority=JobPriority.HIGH
    )
    yield job
    await job_manager.delete_job(job.id)

@pytest.mark.asyncio
async def test_job_lifecycle(job_manager, test_job):
    """Test complete job lifecycle"""
    # Verify job creation
    job = await job_manager.get_job(test_job.id)
    assert job.status == JobStatus.PENDING
    assert job.file_name == "test.mp3"
    assert job.priority == JobPriority.HIGH

    # Claim job
    claimed_job = await job_manager.claim_job("test_worker")
    assert claimed_job.id == test_job.id
    assert claimed_job.status == JobStatus.PROCESSING
    assert claimed_job.locked_by == "test_worker"
    assert claimed_job.locked_at is not None

    # Update progress
    update = JobUpdate(progress=0.5)
    updated_job = await job_manager.update_job(test_job.id, update)
    assert updated_job.progress == 0.5

    # Complete job
    update = JobUpdate(
        status=JobStatus.COMPLETED,
        progress=1.0,
        completed_at=datetime.utcnow()
    )
    completed_job = await job_manager.update_job(test_job.id, update)
    assert completed_job.status == JobStatus.COMPLETED
    assert completed_job.progress == 1.0
    assert completed_job.completed_at is not None

@pytest.mark.asyncio
async def test_concurrent_job_processing(job_manager):
    """Test processing multiple jobs concurrently"""
    # Create test jobs
    jobs = []
    for i in range(5):
        job = await job_manager.create_job(
            user_id=str(uuid.uuid4()),
            file_data=b"test audio data",
            file_name=f"test{i}.mp3",
            priority=JobPriority.NORMAL
        )
        jobs.append(job)

    try:
        # Create workers
        async def worker(worker_id):
            while True:
                job = await job_manager.claim_job(worker_id)
                if not job:
                    break
                
                # Simulate processing
                await asyncio.sleep(0.1)
                
                # Complete job
                update = JobUpdate(
                    status=JobStatus.COMPLETED,
                    progress=1.0,
                    completed_at=datetime.utcnow()
                )
                await job_manager.update_job(job.id, update)

        # Run workers concurrently
        workers = [worker(f"worker{i}") for i in range(3)]
        await asyncio.gather(*workers)

        # Verify all jobs completed
        for job in jobs:
            completed = await job_manager.get_job(job.id)
            assert completed.status == JobStatus.COMPLETED

    finally:
        # Cleanup
        for job in jobs:
            await job_manager.delete_job(job.id)

@pytest.mark.asyncio
async def test_job_failure_recovery(job_manager, test_job):
    """Test recovery of failed jobs"""
    # Simulate failed worker
    claimed_job = await job_manager.claim_job("failed_worker")
    assert claimed_job.id == test_job.id

    # Wait for job timeout
    await asyncio.sleep(0.1)

    # Release stale jobs
    released = await job_manager.release_stale_jobs(max_lock_duration_minutes=0)
    assert released == 1

    # Verify job is available again
    job = await job_manager.get_job(test_job.id)
    assert job.status == JobStatus.PENDING
    assert job.locked_by is None
    assert job.retry_count == 1

@pytest.mark.asyncio
async def test_job_priority_ordering(job_manager):
    """Test jobs are processed in priority order"""
    jobs = []
    try:
        # Create jobs with different priorities
        priorities = [
            JobPriority.LOW,
            JobPriority.HIGH,
            JobPriority.NORMAL,
            JobPriority.HIGH
        ]
        
        for i, priority in enumerate(priorities):
            job = await job_manager.create_job(
                user_id=str(uuid.uuid4()),
                file_data=b"test audio data",
                file_name=f"test{i}.mp3",
                priority=priority
            )
            jobs.append(job)

        # Claim jobs and verify order
        claimed_jobs = []
        while True:
            job = await job_manager.claim_job("test_worker")
            if not job:
                break
            claimed_jobs.append(job)

        # Verify high priority jobs are claimed first
        assert claimed_jobs[0].priority == JobPriority.HIGH
        assert claimed_jobs[1].priority == JobPriority.HIGH
        assert claimed_jobs[2].priority == JobPriority.NORMAL
        assert claimed_jobs[3].priority == JobPriority.LOW

    finally:
        # Cleanup
        for job in jobs:
            await job_manager.delete_job(job.id)

@pytest.mark.asyncio
async def test_job_retry_limits(job_manager, test_job):
    """Test job retry limits"""
    max_retries = 3
    
    for i in range(max_retries + 1):
        # Claim and fail job
        job = await job_manager.claim_job("test_worker")
        update = JobUpdate(
            status=JobStatus.FAILED,
            error=f"Attempt {i+1} failed"
        )
        failed_job = await job_manager.update_job(job.id, update)
        
        if i < max_retries:
            # Job should be retried
            assert failed_job.retry_count == i + 1
            assert failed_job.status == JobStatus.PENDING
        else:
            # Job should be permanently failed
            assert failed_job.retry_count == max_retries
            assert failed_job.status == JobStatus.FAILED

@pytest.mark.asyncio
async def test_job_cancellation(job_manager, test_job):
    """Test job cancellation"""
    # Claim job
    claimed_job = await job_manager.claim_job("test_worker")
    assert claimed_job.id == test_job.id

    # Cancel job
    cancelled_job = await job_manager.cancel_job(test_job.id)
    assert cancelled_job.status == JobStatus.CANCELLED

    # Verify job cannot be claimed
    job = await job_manager.claim_job("test_worker")
    assert job is None

@pytest.mark.asyncio
async def test_job_cleanup(job_manager):
    """Test old job cleanup"""
    jobs = []
    try:
        # Create old completed jobs
        for i in range(3):
            job = await job_manager.create_job(
                user_id=str(uuid.uuid4()),
                file_data=b"test audio data",
                file_name=f"test{i}.mp3"
            )
            # Mark as completed 31 days ago
            update = JobUpdate(
                status=JobStatus.COMPLETED,
                completed_at=datetime.utcnow() - timedelta(days=31)
            )
            await job_manager.update_job(job.id, update)
            jobs.append(job)

        # Run cleanup
        await job_manager.cleanup_old_jobs(max_age_days=30)

        # Verify jobs were deleted
        for job in jobs:
            result = await job_manager.get_job(job.id)
            assert result is None

    finally:
        # Cleanup any remaining jobs
        for job in jobs:
            try:
                await job_manager.delete_job(job.id)
            except:
                pass
