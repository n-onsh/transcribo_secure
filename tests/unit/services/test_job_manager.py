import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from backend.src.models.job import Job, JobStatus, JobPriority
from backend.src.services.job_manager import JobManager
from backend.src.services.interfaces import StorageInterface, DatabaseInterface

@pytest.fixture
def mock_db():
    """Create mock database service"""
    db = Mock(spec=DatabaseInterface)
    db.claim_job = AsyncMock()
    db.get_job = AsyncMock()
    db.update_job = AsyncMock()
    db.delete_job = AsyncMock()
    db.list_jobs = AsyncMock()
    db.release_stale_jobs = AsyncMock()
    db.initialize_database = AsyncMock()
    db.subscribe_to_job_updates = AsyncMock()
    db.unsubscribe_from_job_updates = AsyncMock()
    db.close = AsyncMock()
    return db

@pytest.fixture
def mock_storage():
    """Create mock storage service"""
    storage = Mock(spec=StorageInterface)
    storage.store_file = AsyncMock()
    storage.retrieve_file = AsyncMock()
    storage.delete_file = AsyncMock()
    storage.get_bucket_size = AsyncMock()
    return storage

@pytest.fixture
def job_manager(mock_db, mock_storage):
    """Create JobManager instance with mocked dependencies"""
    return JobManager(storage=mock_storage, db=mock_db)

@pytest.fixture
def test_job():
    """Create test job"""
    return Job(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        file_name="test.mp3",
        file_size=1024,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )

@pytest.mark.asyncio
async def test_job_claiming(job_manager, mock_db, test_job):
    """Test job claiming process"""
    # Setup
    mock_db.claim_job.return_value = test_job
    
    # Test
    claimed_job = await job_manager.claim_job("worker1")
    
    # Verify
    assert claimed_job.id == test_job.id
    mock_db.claim_job.assert_called_once_with("worker1")

@pytest.mark.asyncio
async def test_concurrent_job_claims(mock_db, mock_storage, test_job):
    """Test concurrent job claiming"""
    # Setup
    workers = [JobManager(storage=mock_storage, db=mock_db) for _ in range(3)]
    jobs = [
        Job(
            id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            file_name=f"test{i}.mp3",
            file_size=1024,
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        for i in range(3)
    ]
    
    mock_db.claim_job.side_effect = jobs
    
    # Test
    results = await asyncio.gather(
        *[w.claim_job(f"worker{i}") for i, w in enumerate(workers)]
    )
    
    # Verify
    claimed_ids = [r.id for r in results if r]
    assert len(claimed_ids) == len(set(claimed_ids))  # No duplicate claims
    assert mock_db.claim_job.call_count == 3

@pytest.mark.asyncio
async def test_worker_failure_recovery(job_manager, mock_db, test_job):
    """Test recovery of jobs from failed workers"""
    # Setup
    test_job.status = JobStatus.PROCESSING
    test_job.locked_by = "failed_worker"
    test_job.locked_at = datetime.utcnow() - timedelta(hours=2)
    mock_db.release_stale_jobs.return_value = 1
    
    # Test
    released = await job_manager.release_stale_jobs(max_lock_duration_minutes=60)
    
    # Verify
    assert released == 1
    mock_db.release_stale_jobs.assert_called_once_with(60)

@pytest.mark.asyncio
async def test_job_retry(job_manager, mock_db, test_job):
    """Test job retry functionality"""
    # Setup
    test_job.status = JobStatus.FAILED
    test_job.retry_count = 1
    test_job.max_retries = 3
    mock_db.get_job.return_value = test_job
    mock_db.update_job.return_value = test_job
    
    # Test
    retried_job = await job_manager.retry_job(test_job.id)
    
    # Verify
    assert retried_job.status == JobStatus.PENDING
    assert retried_job.error is None
    assert retried_job.progress == 0.0
    mock_db.update_job.assert_called_once()

@pytest.mark.asyncio
async def test_job_cancellation(job_manager, mock_db, test_job):
    """Test job cancellation"""
    # Setup
    test_job.status = JobStatus.PROCESSING
    mock_db.get_job.return_value = test_job
    mock_db.update_job.return_value = test_job
    
    # Test
    cancelled_job = await job_manager.cancel_job(test_job.id)
    
    # Verify
    assert cancelled_job.status == JobStatus.CANCELLED
    mock_db.update_job.assert_called_once()

@pytest.mark.asyncio
async def test_job_deletion(job_manager, mock_db, mock_storage, test_job):
    """Test job deletion"""
    # Setup
    mock_db.get_job.return_value = test_job
    
    # Test
    await job_manager.delete_job(test_job.id)
    
    # Verify
    mock_storage.delete_file.assert_called_with(
        test_job.user_id,
        test_job.file_name,
        "audio"
    )
    mock_storage.delete_file.assert_called_with(
        test_job.user_id,
        f"{test_job.id}.json",
        "transcription"
    )
    mock_db.delete_job.assert_called_once_with(test_job.id)

@pytest.mark.asyncio
async def test_job_creation(job_manager, mock_db, mock_storage):
    """Test job creation"""
    # Setup
    user_id = str(uuid.uuid4())
    file_data = b"test data"
    file_name = "test.mp3"
    
    # Test
    job = await job_manager.create_job(
        user_id=user_id,
        file_data=file_data,
        file_name=file_name
    )
    
    # Verify
    mock_storage.store_file.assert_called_with(
        user_id,
        file_data,
        file_name,
        "audio"
    )
    assert job.user_id == user_id
    assert job.file_name == file_name
    assert job.status == JobStatus.PENDING

@pytest.mark.asyncio
async def test_job_listing(job_manager, mock_db, test_job):
    """Test job listing"""
    # Setup
    mock_db.list_jobs.return_value = [test_job]
    
    # Test
    jobs = await job_manager.list_jobs(
        user_id=test_job.user_id,
        limit=10,
        offset=0
    )
    
    # Verify
    assert len(jobs) == 1
    assert jobs[0].id == test_job.id
    mock_db.list_jobs.assert_called_once()

@pytest.mark.asyncio
async def test_job_notification(job_manager, mock_db):
    """Test job notification handling"""
    # Setup
    notification = {
        "job_id": str(uuid.uuid4()),
        "status": "processing",
        "worker_id": "worker2"
    }
    
    # Add job to active jobs
    job_manager.active_jobs[notification["job_id"]] = Mock()
    
    # Test
    await job_manager._handle_job_update(notification)
    
    # Verify job was removed from active jobs
    assert notification["job_id"] not in job_manager.active_jobs

@pytest.mark.asyncio
async def test_service_lifecycle(job_manager, mock_db):
    """Test service startup and shutdown"""
    # Test startup
    await job_manager.start()
    mock_db.initialize_database.assert_called_once()
    mock_db.subscribe_to_job_updates.assert_called_once()
    assert len(job_manager.worker_tasks) == job_manager.max_concurrent_jobs
    
    # Test shutdown
    await job_manager.stop()
    mock_db.unsubscribe_from_job_updates.assert_called_once()
    mock_db.close.assert_called_once()
    assert not job_manager.worker_tasks
