"""Integration tests for fault tolerance."""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from backend.src.models.job import Job, JobStatus, JobPriority, TranscriptionOptions
from backend.src.services.database import DatabaseService
from backend.src.services.storage import StorageService
from backend.src.services.job_distribution import JobDistributor
from backend.src.services.fault_tolerance import FaultToleranceService

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
async def fault_tolerance(db, distributor):
    """Create fault tolerance service"""
    service = FaultToleranceService(
        db=db,
        distributor=distributor,
        health_check_interval=1,  # 1 second for tests
        health_check_timeout=1,  # 1 second for tests
        failure_threshold=2,
        recovery_threshold=2,
        failover_delay=1  # 1 second for tests
    )
    await service.initialize()
    return service

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
async def test_worker_failure_recovery_flow(distributor, fault_tolerance, test_jobs):
    """Test complete worker failure and recovery flow"""
    # Register worker
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    await fault_tolerance.register_worker(worker_id)
    
    # Claim jobs
    jobs = []
    for _ in range(2):
        job = await distributor.claim_job(worker_id)
        if job:
            jobs.append(job)
    
    # Verify jobs claimed
    assert len(jobs) == 2
    assert len(distributor.worker_jobs[worker_id]) == 2
    
    # Stop sending heartbeats to trigger failure
    await asyncio.sleep(2.5)  # Wait for failure detection
    
    # Verify worker failed and jobs released
    assert worker_id in fault_tolerance.failed_workers
    assert len(distributor.worker_jobs[worker_id]) == 0
    
    # Check jobs are available again
    async with distributor.db.pool.acquire() as conn:
        for job in jobs:
            row = await conn.fetchrow("""
                SELECT status, retry_count
                FROM jobs
                WHERE id = $1
            """, job.id)
            assert row["status"] == JobStatus.PENDING.value
            assert row["retry_count"] == 1
    
    # Start recovery
    for _ in range(3):  # Send multiple heartbeats
        await fault_tolerance.heartbeat(worker_id)
        await asyncio.sleep(0.5)
    
    # Verify worker recovered
    assert worker_id not in fault_tolerance.failed_workers
    assert worker_id not in fault_tolerance.recovering_workers
    
    # Should be able to claim jobs again
    new_jobs = []
    for _ in range(2):
        job = await distributor.claim_job(worker_id)
        if job:
            new_jobs.append(job)
    assert len(new_jobs) == 2

@pytest.mark.asyncio
async def test_system_degradation_recovery(distributor, fault_tolerance, test_jobs):
    """Test system degradation and recovery"""
    # Register multiple workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await distributor.register_worker(worker_id)
        await fault_tolerance.register_worker(worker_id)
    
    # Distribute jobs
    worker_jobs = {}
    for worker_id in workers:
        jobs = []
        for _ in range(2):
            job = await distributor.claim_job(worker_id)
            if job:
                jobs.append(job)
        worker_jobs[worker_id] = jobs
    
    # Verify initial distribution
    status = await fault_tolerance.get_system_health()
    assert status["status"] == "healthy"
    assert status["healthy_workers"] == 3
    
    # Simulate cascading failures
    for worker_id in workers:
        await asyncio.sleep(2.5)  # Wait for failure detection
        
        # Verify worker failed
        assert worker_id in fault_tolerance.failed_workers
        assert len(distributor.worker_jobs[worker_id]) == 0
    
    # Verify system degraded
    status = await fault_tolerance.get_system_health()
    assert status["status"] == "degraded"
    assert status["healthy_workers"] == 0
    
    # Start recovery one by one
    for worker_id in workers:
        for _ in range(3):  # Send multiple heartbeats
            await fault_tolerance.heartbeat(worker_id)
            await asyncio.sleep(0.5)
        
        # Verify worker recovered
        assert worker_id not in fault_tolerance.failed_workers
        
        # Check system status
        status = await fault_tolerance.get_system_health()
        if worker_id != workers[-1]:
            assert status["status"] == "healthy"  # System healthy with at least one worker
    
    # Verify full recovery
    status = await fault_tolerance.get_system_health()
    assert status["status"] == "healthy"
    assert status["healthy_workers"] == 3

@pytest.mark.asyncio
async def test_partial_system_operation(distributor, fault_tolerance, test_jobs):
    """Test system continues operation with partial worker availability"""
    # Register multiple workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await distributor.register_worker(worker_id)
        await fault_tolerance.register_worker(worker_id)
    
    # Fail some workers
    failed_workers = workers[:2]
    for worker_id in failed_workers:
        await asyncio.sleep(2.5)  # Wait for failure detection
        assert worker_id in fault_tolerance.failed_workers
    
    # Verify remaining worker can still process jobs
    active_worker = workers[2]
    jobs = []
    for _ in range(2):
        job = await distributor.claim_job(active_worker)
        if job:
            jobs.append(job)
            await distributor.complete_job(
                job_id=job.id,
                worker_id=active_worker,
                status=JobStatus.COMPLETED
            )
    
    # Verify jobs completed
    async with distributor.db.pool.acquire() as conn:
        for job in jobs:
            row = await conn.fetchrow("""
                SELECT status
                FROM jobs
                WHERE id = $1
            """, job.id)
            assert row["status"] == JobStatus.COMPLETED.value

@pytest.mark.asyncio
async def test_failover_timing(distributor, fault_tolerance, test_jobs):
    """Test failover timing and job redistribution"""
    # Register workers
    workers = ["worker1", "worker2"]
    for worker_id in workers:
        await distributor.register_worker(worker_id)
        await fault_tolerance.register_worker(worker_id)
    
    # Worker1 claims jobs
    original_jobs = []
    for _ in range(2):
        job = await distributor.claim_job("worker1")
        if job:
            original_jobs.append(job)
    
    # Record job assignment time
    assignment_time = datetime.utcnow()
    
    # Wait for worker1 to fail
    await asyncio.sleep(2.5)
    assert "worker1" in fault_tolerance.failed_workers
    
    # Worker2 should get the jobs
    reassigned_jobs = []
    for _ in range(2):
        job = await distributor.claim_job("worker2")
        if job:
            reassigned_jobs.append(job)
    
    # Verify timing
    reassignment_time = datetime.utcnow()
    failover_duration = (reassignment_time - assignment_time).total_seconds()
    
    # Should take about 3-4 seconds (failure detection + failover delay)
    assert 3 <= failover_duration <= 5
    
    # Verify same jobs were reassigned
    assert len(reassigned_jobs) == len(original_jobs)
    assert set(j.id for j in reassigned_jobs) == set(j.id for j in original_jobs)
