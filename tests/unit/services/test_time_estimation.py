import pytest
import uuid
from datetime import datetime
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
    db.create_job = AsyncMock()
    return db

@pytest.fixture
def mock_storage():
    """Create mock storage service"""
    storage = Mock(spec=StorageInterface)
    storage.store_file = AsyncMock()
    return storage

@pytest.fixture
def job_manager(mock_db, mock_storage):
    """Create JobManager instance with mocked dependencies"""
    return JobManager(storage=mock_storage, db=mock_db)

@pytest.fixture
def test_job():
    """Create test job with time estimates"""
    return Job(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        file_name="test.mp3",
        file_size=1024,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        estimated_time=300.0,  # 5 minutes
        estimated_range=(240.0, 360.0),  # 4-6 minutes
        estimate_confidence=0.8
    )

@pytest.mark.asyncio
async def test_job_creation_with_estimates(job_manager, mock_db, test_job):
    """Test job creation with time estimates"""
    # Setup
    mock_db.create_job.return_value = test_job
    
    # Test
    job = await job_manager.create_job(
        user_id=test_job.user_id,
        file_data=b"test",
        file_name=test_job.file_name
    )
    
    # Verify
    assert job.estimated_time == 300.0
    assert job.estimated_range == (240.0, 360.0)
    assert job.estimate_confidence == 0.8
    mock_db.create_job.assert_called_once()

@pytest.mark.asyncio
async def test_job_update_with_estimates(job_manager, mock_db, test_job):
    """Test job update with time estimates"""
    # Setup
    mock_db.get_job.return_value = test_job
    mock_db.update_job.return_value = test_job
    
    # Update estimates
    test_job.estimated_time = 400.0
    test_job.estimated_range = (350.0, 450.0)
    test_job.estimate_confidence = 0.9
    
    # Test
    updated_job = await job_manager.update_job(test_job.id, test_job)
    
    # Verify
    assert updated_job.estimated_time == 400.0
    assert updated_job.estimated_range == (350.0, 450.0)
    assert updated_job.estimate_confidence == 0.9
    mock_db.update_job.assert_called_once()

@pytest.mark.asyncio
async def test_job_progress_with_estimates(job_manager, mock_db, test_job):
    """Test job progress updates with time estimates"""
    # Setup
    mock_db.get_job.return_value = test_job
    mock_db.update_job.return_value = test_job
    
    # Update progress
    test_job.progress = 50.0
    
    # Test
    updated_job = await job_manager.update_job(test_job.id, test_job)
    
    # Verify remaining time calculation
    remaining_time = test_job.estimated_time * (1 - test_job.progress/100)
    assert remaining_time == 150.0  # Half of 300s
    mock_db.update_job.assert_called_once()

@pytest.mark.asyncio
async def test_invalid_time_estimates(job_manager, mock_db):
    """Test validation of time estimates"""
    # Setup invalid job
    invalid_job = Job(
        id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        file_name="test.mp3",
        file_size=1024,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        estimated_time=-1.0,  # Invalid negative time
        estimated_range=(-10.0, 100.0),  # Invalid negative range
        estimate_confidence=1.5  # Invalid confidence > 1
    )
    
    # Test
    with pytest.raises(ValueError):
        await job_manager.create_job(
            user_id=invalid_job.user_id,
            file_data=b"test",
            file_name=invalid_job.file_name,
            estimated_time=invalid_job.estimated_time,
            estimated_range=invalid_job.estimated_range,
            estimate_confidence=invalid_job.estimate_confidence
        )

@pytest.mark.asyncio
async def test_job_completion_time_tracking(job_manager, mock_db, test_job):
    """Test tracking of actual completion times"""
    # Setup
    mock_db.get_job.return_value = test_job
    mock_db.update_job.return_value = test_job
    
    # Complete job
    test_job.status = JobStatus.COMPLETED
    test_job.progress = 100.0
    test_job.completed_at = datetime.utcnow()
    
    # Test
    completed_job = await job_manager.update_job(test_job.id, test_job)
    
    # Verify
    assert completed_job.completed_at is not None
    duration = (completed_job.completed_at - completed_job.created_at).total_seconds()
    assert duration > 0
    mock_db.update_job.assert_called_once()
