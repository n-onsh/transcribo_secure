"""Tests for job distribution service."""

import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from backend.src.models.job import Job, JobStatus, JobPriority
from backend.src.services.job_distribution import JobDistributor

@pytest.fixture
def mock_db():
    """Create mock database service"""
    db = Mock()
    db.pool = Mock()
    db.pool.acquire = AsyncMock()
    return db

@pytest.fixture
def mock_storage():
    """Create mock storage service"""
    return Mock()

@pytest.fixture
def mock_conn():
    """Create mock database connection"""
    conn = Mock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    conn.transaction = AsyncMock()
    # Setup transaction context
    conn.transaction.return_value.__aenter__ = AsyncMock()
    conn.transaction.return_value.__aexit__ = AsyncMock()
    return conn

@pytest.fixture
async def distributor(mock_db, mock_storage, mock_conn):
    """Create job distributor with mocked dependencies"""
    # Setup connection pool
    mock_db.pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_db.pool.acquire.return_value.__aexit__ = AsyncMock()
    
    distributor = JobDistributor(
        db=mock_db,
        storage=mock_storage,
        max_jobs_per_worker=2,
        max_retries=3,
        retry_delay=60,
        stale_job_timeout=1800
    )
    await distributor.initialize()
    return distributor

@pytest.fixture
def test_job():
    """Create test job"""
    return {
        'id': str(uuid.uuid4()),
        'owner_id': str(uuid.uuid4()),
        'file_name': 'test.mp3',
        'file_size': 1024,
        'status': JobStatus.PENDING.value,
        'priority': JobPriority.NORMAL.value,
        'created_at': datetime.utcnow(),
        'updated_at': datetime.utcnow(),
        'retry_count': 0,
        'max_retries': 3,
        'options': {'language': 'de'}
    }

@pytest.mark.asyncio
async def test_register_worker(distributor):
    """Test worker registration"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    assert worker_id in distributor.worker_loads
    assert worker_id in distributor.worker_jobs
    assert distributor.worker_loads[worker_id] == 0.0
    assert distributor.worker_jobs[worker_id] == []

@pytest.mark.asyncio
async def test_unregister_worker(distributor):
    """Test worker unregistration"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    await distributor.unregister_worker(worker_id)
    
    assert worker_id not in distributor.worker_loads
    assert worker_id not in distributor.worker_jobs

@pytest.mark.asyncio
async def test_claim_job(distributor, mock_conn, test_job):
    """Test job claiming"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Setup mock response
    mock_conn.fetchrow.return_value = test_job
    
    # Claim job
    job = await distributor.claim_job(worker_id)
    
    # Verify job claimed
    assert job is not None
    assert job.id == test_job['id']
    assert job.status == JobStatus.PENDING
    assert test_job['id'] in distributor.worker_jobs[worker_id]
    
    # Verify database updates
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE jobs" in call_args[0]
    assert call_args[1] == worker_id
    assert call_args[2] == test_job['id']

@pytest.mark.asyncio
async def test_claim_job_at_capacity(distributor, mock_conn, test_job):
    """Test job claiming at worker capacity"""
    worker_id = "test-worker"
    await distributor.register_worker(worker_id)
    
    # Fill worker capacity
    job_ids = [str(uuid.uuid4()) for _ in range(2)]
    distributor.worker_jobs[worker_id].extend(job_ids)
    distributor.worker_loads[worker_id] = 100.0
    
    # Try to claim job
    job = await distributor.claim_job(worker_id)
    
    # Verify no job claimed
    assert job is None
    mock_conn.fetchrow.assert_not_called()

@pytest.mark.asyncio
async def test_complete_job_success(distributor, mock_conn, test_job):
    """Test successful job completion"""
    worker_id = "test-worker"
    job_id = test_job['id']
    await distributor.register_worker(worker_id)
    distributor.worker_jobs[worker_id].append(job_id)
    
    # Complete job
    await distributor.complete_job(
        job_id=job_id,
        worker_id=worker_id,
        status=JobStatus.COMPLETED
    )
    
    # Verify updates
    assert job_id not in distributor.worker_jobs[worker_id]
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE jobs" in call_args[0]
    assert call_args[1] == JobStatus.COMPLETED.value

@pytest.mark.asyncio
async def test_complete_job_failure(distributor, mock_conn, test_job):
    """Test job completion with failure"""
    worker_id = "test-worker"
    job_id = test_job['id']
    error = "Test error"
    await distributor.register_worker(worker_id)
    distributor.worker_jobs[worker_id].append(job_id)
    
    # Complete job with error
    await distributor.complete_job(
        job_id=job_id,
        worker_id=worker_id,
        status=JobStatus.FAILED,
        error=error
    )
    
    # Verify updates
    assert job_id not in distributor.worker_jobs[worker_id]
    mock_conn.execute.assert_called_once()
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE jobs" in call_args[0]
    assert call_args[1] == JobStatus.FAILED.value
    assert call_args[2] == error

@pytest.mark.asyncio
async def test_release_job_with_retries(distributor, mock_conn, test_job):
    """Test job release with retries"""
    job_id = test_job['id']
    
    # Setup mock response
    mock_conn.fetchrow.return_value = {
        'status': JobStatus.PROCESSING.value,
        'retry_count': 1,
        'max_retries': 3
    }
    
    # Release job
    await distributor._release_job(job_id)
    
    # Verify updates
    assert mock_conn.execute.call_count == 1
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE jobs" in call_args[0]
    assert "status = 'pending'" in call_args[0]

@pytest.mark.asyncio
async def test_release_job_max_retries(distributor, mock_conn, test_job):
    """Test job release at max retries"""
    job_id = test_job['id']
    
    # Setup mock response
    mock_conn.fetchrow.return_value = {
        'status': JobStatus.PROCESSING.value,
        'retry_count': 3,
        'max_retries': 3
    }
    
    # Release job
    await distributor._release_job(job_id)
    
    # Verify updates
    assert mock_conn.execute.call_count == 1
    call_args = mock_conn.execute.call_args[0]
    assert "UPDATE jobs" in call_args[0]
    assert "status = 'failed'" in call_args[0]

@pytest.mark.asyncio
async def test_cleanup_stale_jobs(distributor, mock_conn):
    """Test stale job cleanup"""
    # Setup mock response
    stale_jobs = [
        {'id': str(uuid.uuid4()), 'locked_by': 'worker1'},
        {'id': str(uuid.uuid4()), 'locked_by': 'worker2'}
    ]
    mock_conn.fetch.return_value = stale_jobs
    
    # Register workers
    for job in stale_jobs:
        worker_id = job['locked_by']
        await distributor.register_worker(worker_id)
        distributor.worker_jobs[worker_id].append(job['id'])
    
    # Run cleanup
    await distributor._cleanup_stale_jobs()
    
    # Verify cleanup
    assert mock_conn.fetch.call_count == 1
    assert "locked_at < $1" in mock_conn.fetch.call_args[0][0]
    
    # Verify jobs released
    for job in stale_jobs:
        worker_id = job['locked_by']
        assert job['id'] not in distributor.worker_jobs[worker_id]

@pytest.mark.asyncio
async def test_monitor_worker_loads(distributor):
    """Test worker load monitoring"""
    # Setup test data
    workers = ['worker1', 'worker2']
    for worker_id in workers:
        await distributor.register_worker(worker_id)
        # Add some jobs
        job_count = 1 if worker_id == 'worker1' else 2
        for _ in range(job_count):
            distributor.worker_jobs[worker_id].append(str(uuid.uuid4()))
    
    # Run monitoring
    await distributor._monitor_worker_loads()
    
    # Verify loads
    assert distributor.worker_loads['worker1'] == 50.0  # 1/2 capacity
    assert distributor.worker_loads['worker2'] == 100.0  # 2/2 capacity
