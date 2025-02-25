"""Integration tests for job distribution."""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from backend.src.models.job import Job, JobStatus, JobPriority, TranscriptionOptions
from backend.src.services.job_distribution import JobDistributor
from backend.src.services.database import DatabaseService
from backend.src.services.storage import StorageService

@pytest.fixture
async def db():
    """Create database service"""
    db = DatabaseService()
    await db.initialize_database()
    return db

@pytest.fixture
async def storage():
    """Create storage service"""
    storage = StorageService()
    await storage.initialize()
    return storage

@pytest.fixture
async def distributor(db, storage):
    """Create job distributor"""
    distributor = JobDistributor(
        db=db,
        storage=storage,
        max_jobs_per_worker=2,
        max_retries=3,
        retry_delay=1,  # 1 second for tests
        stale_job_timeout=5  # 5 seconds for tests
    )
    await distributor.initialize()
    return distributor

@pytest.fixture
async def test_jobs(db):
    """Create test jobs"""
    jobs = []
    for i in range(5):
        job = Job(
            id=str(uuid4()),
            owner_id=str(uuid4()),
            file_name=f"test_{i}.mp3",
            file_size=1024,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            options=TranscriptionOptions(language="de")
        )
        # Insert job
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO jobs (
                        id, owner_id, file_name, file_size, status,
                        priority, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, str(job.id), str(job.owner_id), job.file_name,
                    job.file_size, job.status.value, job.priority.value,
                    job.created_at, job.updated_at)
                
                await conn.execute("""
                    INSERT INTO job_options (job_id, options)
                    VALUES ($1, $2)
                """, str(job.id), job.options.dict())
        
        jobs.append(job)
    return jobs

@pytest.mark.asyncio
async def test_job_distribution_flow(distributor, test_jobs):
    """Test complete job distribution flow"""
    # Register workers
    workers = ["worker1", "worker2"]
    for worker_id in workers:
        await distributor.register_worker(worker_id)
    
    # Claim jobs
    claimed_jobs = {}
    for worker_id in workers:
        worker_jobs = []
        for _ in range(2):  # Each worker claims 2 jobs
            job = await distributor.claim_job(worker_id)
            if job:
                worker_jobs.append(job)
        claimed_jobs[worker_id] = worker_jobs
    
    # Verify distribution
    for worker_id, jobs in claimed_jobs.items():
        assert len(jobs) == 2  # Each worker got 2 jobs
        assert len(distributor.worker_jobs[worker_id]) == 2
        assert distributor.worker_loads[worker_id] == 100.0
    
    # Complete some jobs
    for worker_id, jobs in claimed_jobs.items():
        for job in jobs[:1]:  # Complete first job for each worker
            await distributor.complete_job(
                job_id=job.id,
                worker_id=worker_id,
                status=JobStatus.COMPLETED
            )
    
    # Verify completion
    for worker_id in workers:
        assert len(distributor.worker_jobs[worker_id]) == 1
        assert distributor.worker_loads[worker_id] == 50.0

@pytest.mark.asyncio
async def test_job_retry_flow(distributor, test_jobs):
    """Test job retry flow"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Claim job
    job = await distributor.claim_job(worker_id)
    assert job is not None
    
    # Fail job
    await distributor.complete_job(
        job_id=job.id,
        worker_id=worker_id,
        status=JobStatus.FAILED,
        error="Test error"
    )
    
    # Wait for retry delay
    await asyncio.sleep(2)
    
    # Job should be available again
    retried_job = await distributor.claim_job(worker_id)
    assert retried_job is not None
    assert retried_job.id == job.id
    assert retried_job.retry_count == 1

@pytest.mark.asyncio
async def test_stale_job_cleanup(distributor, test_jobs):
    """Test stale job cleanup"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Claim job
    job = await distributor.claim_job(worker_id)
    assert job is not None
    
    # Wait for job to become stale
    await asyncio.sleep(6)
    
    # Run cleanup manually
    await distributor._cleanup_stale_jobs()
    
    # Job should be released
    assert job.id not in distributor.worker_jobs[worker_id]
    
    # Job should be available again
    released_job = await distributor.claim_job(worker_id)
    assert released_job is not None
    assert released_job.id == job.id
    assert released_job.retry_count == 1

@pytest.mark.asyncio
async def test_worker_load_balancing(distributor, test_jobs):
    """Test worker load balancing"""
    # Register workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await distributor.register_worker(worker_id)
    
    # Claim jobs with different loads
    # worker1: 2 jobs (100%)
    # worker2: 1 job (50%)
    # worker3: 0 jobs (0%)
    claimed_jobs = {
        "worker1": [
            await distributor.claim_job("worker1"),
            await distributor.claim_job("worker1")
        ],
        "worker2": [
            await distributor.claim_job("worker2")
        ],
        "worker3": []
    }
    
    # Try to claim new job
    # Should go to worker3 (lowest load)
    job = await distributor.claim_job("worker3")
    assert job is not None
    assert job.id in distributor.worker_jobs["worker3"]
    
    # Verify final loads
    assert distributor.worker_loads["worker1"] == 100.0
    assert distributor.worker_loads["worker2"] == 50.0
    assert distributor.worker_loads["worker3"] == 50.0

@pytest.mark.asyncio
async def test_worker_failure_recovery(distributor, test_jobs):
    """Test recovery from worker failure"""
    # Register worker
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Claim jobs
    jobs = []
    for _ in range(2):
        job = await distributor.claim_job(worker_id)
        if job:
            jobs.append(job)
    
    # Simulate worker failure
    await distributor.unregister_worker(worker_id)
    
    # Jobs should be released
    for job in jobs:
        assert job.id not in distributor.worker_jobs.get(worker_id, [])
    
    # Register new worker
    new_worker = "new-worker"
    await distributor.register_worker(new_worker)
    
    # Should be able to claim released jobs
    for _ in range(2):
        job = await distributor.claim_job(new_worker)
        assert job is not None

@pytest.mark.asyncio
async def test_priority_based_distribution(distributor, db):
    """Test priority-based job distribution"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Create jobs with different priorities
    priorities = [
        JobPriority.LOW,
        JobPriority.NORMAL,
        JobPriority.HIGH
    ]
    
    priority_jobs = {}
    for priority in priorities:
        job = Job(
            id=str(uuid4()),
            owner_id=str(uuid4()),
            file_name=f"test_{priority.value}.mp3",
            file_size=1024,
            status=JobStatus.PENDING,
            priority=priority,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            options=TranscriptionOptions(language="de")
        )
        
        # Insert job
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("""
                    INSERT INTO jobs (
                        id, owner_id, file_name, file_size, status,
                        priority, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, str(job.id), str(job.owner_id), job.file_name,
                    job.file_size, job.status.value, job.priority.value,
                    job.created_at, job.updated_at)
                
                await conn.execute("""
                    INSERT INTO job_options (job_id, options)
                    VALUES ($1, $2)
                """, str(job.id), job.options.dict())
        
        priority_jobs[priority] = job
    
    # Claim jobs
    claimed_jobs = []
    while len(claimed_jobs) < 3:
        job = await distributor.claim_job(worker_id)
        if job:
            claimed_jobs.append(job)
    
    # Verify priority order
    assert claimed_jobs[0].priority == JobPriority.HIGH
    assert claimed_jobs[1].priority == JobPriority.NORMAL
    assert claimed_jobs[2].priority == JobPriority.LOW
