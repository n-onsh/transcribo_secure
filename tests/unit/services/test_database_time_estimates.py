import pytest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock
from backend.src.services.database import DatabaseService
from backend.src.models.job import Job, JobStatus, JobPriority, TranscriptionOptions

@pytest.fixture
def mock_pool():
    """Create mock connection pool"""
    pool = Mock()
    pool.acquire = AsyncMock()
    return pool

@pytest.fixture
def mock_conn():
    """Create mock database connection"""
    conn = Mock()
    conn.fetchrow = AsyncMock()
    conn.fetch = AsyncMock()
    conn.execute = AsyncMock()
    conn.transaction = AsyncMock()
    return conn

@pytest.fixture
async def db_service(mock_pool, mock_conn):
    """Create database service with mocked pool"""
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_conn.transaction.return_value.__aenter__ = AsyncMock()
    mock_conn.transaction.return_value.__aexit__ = AsyncMock()
    
    service = DatabaseService()
    service.pool = mock_pool
    return service

@pytest.fixture
def test_job():
    """Create test job"""
    return Job(
        id=str(uuid.uuid4()),
        owner_id=str(uuid.uuid4()),
        file_name="test.mp3",
        file_size=1024,
        status=JobStatus.PENDING,
        priority=JobPriority.NORMAL,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        options=TranscriptionOptions(language="de")
    )

@pytest.mark.asyncio
async def test_estimate_processing_time(db_service, mock_conn):
    """Test getting processing time estimate"""
    # Setup mock response
    mock_conn.fetchrow.return_value = {
        "estimated_seconds": 300.0,
        "min_seconds": 240.0,
        "max_seconds": 360.0,
        "confidence": 0.8
    }
    
    # Test
    estimate = await db_service.estimate_processing_time(150.0, "de")
    
    # Verify
    assert estimate["estimated_time"] == 300.0
    assert estimate["range"] == (240.0, 360.0)
    assert estimate["confidence"] == 0.8
    mock_conn.fetchrow.assert_called_once_with(
        "SELECT * FROM estimate_processing_time($1, $2)",
        150.0, "de"
    )

@pytest.mark.asyncio
async def test_estimate_processing_time_error(db_service, mock_conn):
    """Test error handling in time estimation"""
    # Setup mock error
    mock_conn.fetchrow.side_effect = Exception("Database error")
    
    # Test
    estimate = await db_service.estimate_processing_time(150.0, "de")
    
    # Verify default values returned
    assert estimate["estimated_time"] == 300.0  # 2x duration
    assert estimate["range"] == (150.0, 450.0)  # 1x to 3x duration
    assert estimate["confidence"] == 0.5

@pytest.mark.asyncio
async def test_get_performance_metrics(db_service, mock_conn):
    """Test getting performance metrics"""
    # Setup mock response
    mock_conn.fetch.return_value = [
        {
            "language": "de",
            "total_jobs": 100,
            "avg_processing_time": 300.0,
            "min_processing_time": 200.0,
            "max_processing_time": 400.0,
            "avg_word_count": 1000,
            "seconds_per_word": 0.3
        },
        {
            "language": "en",
            "total_jobs": 50,
            "avg_processing_time": 250.0,
            "min_processing_time": 150.0,
            "max_processing_time": 350.0,
            "avg_word_count": 800,
            "seconds_per_word": 0.25
        }
    ]
    
    # Test
    metrics = await db_service.get_performance_metrics()
    
    # Verify
    assert "de" in metrics
    assert "en" in metrics
    assert metrics["de"]["total_jobs"] == 100
    assert metrics["en"]["total_jobs"] == 50
    assert metrics["de"]["avg_processing_time"] == 300.0
    assert metrics["en"]["avg_processing_time"] == 250.0
    mock_conn.fetch.assert_called_once_with(
        "SELECT * FROM job_performance_metrics"
    )

@pytest.mark.asyncio
async def test_get_performance_metrics_error(db_service, mock_conn):
    """Test error handling in performance metrics"""
    # Setup mock error
    mock_conn.fetch.side_effect = Exception("Database error")
    
    # Test
    metrics = await db_service.get_performance_metrics()
    
    # Verify empty dict returned
    assert metrics == {}

@pytest.mark.asyncio
async def test_create_job_with_time_estimate(db_service, mock_conn, test_job):
    """Test job creation with time estimation"""
    # Setup mock responses
    mock_conn.fetchrow.side_effect = [
        # First call - estimate_processing_time
        {
            "estimated_seconds": 300.0,
            "min_seconds": 240.0,
            "max_seconds": 360.0,
            "confidence": 0.8
        },
        # Second call - create_job
        {
            "id": test_job.id,
            "owner_id": test_job.owner_id,
            "file_name": test_job.file_name,
            "file_size": test_job.file_size,
            "status": test_job.status.value,
            "priority": test_job.priority.value,
            "created_at": test_job.created_at,
            "updated_at": test_job.updated_at,
            "estimated_time": 300.0,
            "estimated_range_min": 240.0,
            "estimated_range_max": 360.0,
            "estimate_confidence": 0.8
        }
    ]
    
    # Test
    job = await db_service.create_job(test_job)
    
    # Verify
    assert job.estimated_time == 300.0
    assert job.estimated_range == (240.0, 360.0)
    assert job.estimate_confidence == 0.8
    assert mock_conn.fetchrow.call_count == 2

@pytest.mark.asyncio
async def test_update_job_with_time_estimates(db_service, mock_conn, test_job):
    """Test job update with time estimates"""
    # Setup test job with estimates
    test_job.estimated_time = 300.0
    test_job.estimated_range = (240.0, 360.0)
    test_job.estimate_confidence = 0.8
    
    # Setup mock response
    mock_conn.fetchrow.return_value = {
        "id": test_job.id,
        "owner_id": test_job.owner_id,
        "file_name": test_job.file_name,
        "file_size": test_job.file_size,
        "status": test_job.status.value,
        "priority": test_job.priority.value,
        "created_at": test_job.created_at,
        "updated_at": test_job.updated_at,
        "estimated_time": test_job.estimated_time,
        "estimated_range_min": test_job.estimated_range[0],
        "estimated_range_max": test_job.estimated_range[1],
        "estimate_confidence": test_job.estimate_confidence
    }
    
    # Test
    updated_job = await db_service.update_job(test_job.id, test_job)
    
    # Verify
    assert updated_job.estimated_time == 300.0
    assert updated_job.estimated_range == (240.0, 360.0)
    assert updated_job.estimate_confidence == 0.8
    assert mock_conn.fetchrow.call_count == 1
