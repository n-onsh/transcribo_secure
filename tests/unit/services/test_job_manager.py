"""
Tests for the job management service.

Critical aspects:
1. Job creation and queuing
2. Status updates
3. Error handling
4. Resource cleanup
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock
from backend.src.services.job_manager import JobManager
from backend.src.models.job import Job, JobStatus, JobPriority

@pytest.fixture
def mock_db():
    """Create a mock database service."""
    db = MagicMock()
    db.get_job = AsyncMock()
    db.create_job = AsyncMock()
    db.update_job = AsyncMock()
    db.list_jobs = AsyncMock()
    return db

@pytest.fixture
def job_manager(mock_db):
    """Create a job manager instance with mocked dependencies."""
    return JobManager(db=mock_db)

class TestJobManager:
    """Test suite for JobManager."""

    async def test_create_job(self, job_manager, mock_db):
        """Test job creation."""
        # Setup
        file_id = "test_file"
        user_id = "test_user"
        file_name = "test.mp3"
        
        # Create job
        job = await job_manager.create_job(
            file_id=file_id,
            user_id=user_id,
            file_name=file_name
        )
        
        # Verify
        assert isinstance(job, Job)
        assert job.file_id == file_id
        assert job.user_id == user_id
        assert job.file_name == file_name
        assert job.status == JobStatus.PENDING
        mock_db.create_job.assert_called_once()

    async def test_get_next_job(self, job_manager, mock_db):
        """Test job queue processing."""
        # Setup mock jobs
        high_priority = Job(
            id="job1",
            user_id="user1",
            file_id="file1",
            file_name="high.mp3",
            priority=JobPriority.HIGH,
            status=JobStatus.PENDING
        )
        normal_priority = Job(
            id="job2",
            user_id="user2",
            file_id="file2",
            file_name="normal.mp3",
            priority=JobPriority.NORMAL,
            status=JobStatus.PENDING
        )
        
        mock_db.list_jobs.return_value = [normal_priority, high_priority]
        
        # Get next job
        next_job = await job_manager.get_next_job()
        
        # Verify high priority job is selected
        assert next_job.id == "job1"
        assert next_job.priority == JobPriority.HIGH

    async def test_update_job_status(self, job_manager, mock_db):
        """Test job status updates."""
        # Setup
        job_id = "test_job"
        job = Job(
            id=job_id,
            user_id="test_user",
            file_id="test_file",
            file_name="test.mp3",
            status=JobStatus.PENDING
        )
        mock_db.get_job.return_value = job
        
        # Update status
        await job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress=50.0
        )
        
        # Verify
        mock_db.update_job.assert_called_once()
        call_args = mock_db.update_job.call_args[0][0]
        assert call_args.status == JobStatus.PROCESSING
        assert call_args.progress == 50.0

    async def test_job_completion(self, job_manager, mock_db):
        """Test job completion flow."""
        # Setup
        job_id = "test_job"
        job = Job(
            id=job_id,
            user_id="test_user",
            file_id="test_file",
            file_name="test.mp3",
            status=JobStatus.PROCESSING
        )
        mock_db.get_job.return_value = job
        
        # Complete job
        await job_manager.complete_job(job_id)
        
        # Verify
        mock_db.update_job.assert_called_once()
        call_args = mock_db.update_job.call_args[0][0]
        assert call_args.status == JobStatus.COMPLETED
        assert call_args.progress == 100.0
        assert call_args.completed_at is not None

    async def test_job_failure(self, job_manager, mock_db):
        """Test job failure handling."""
        # Setup
        job_id = "test_job"
        error_message = "Processing failed"
        job = Job(
            id=job_id,
            user_id="test_user",
            file_id="test_file",
            file_name="test.mp3",
            status=JobStatus.PROCESSING
        )
        mock_db.get_job.return_value = job
        
        # Fail job
        await job_manager.fail_job(job_id, error_message)
        
        # Verify
        mock_db.update_job.assert_called_once()
        call_args = mock_db.update_job.call_args[0][0]
        assert call_args.status == JobStatus.FAILED
        assert call_args.error == error_message

    async def test_retry_mechanism(self, job_manager, mock_db):
        """Test job retry mechanism."""
        # Setup
        job_id = "test_job"
        job = Job(
            id=job_id,
            user_id="test_user",
            file_id="test_file",
            file_name="test.mp3",
            status=JobStatus.FAILED,
            retry_count=1,
            max_retries=3
        )
        mock_db.get_job.return_value = job
        
        # Retry job
        await job_manager.retry_job(job_id)
        
        # Verify
        mock_db.update_job.assert_called_once()
        call_args = mock_db.update_job.call_args[0][0]
        assert call_args.status == JobStatus.PENDING
        assert call_args.retry_count == 2
        assert call_args.error is None

    async def test_cleanup_old_jobs(self, job_manager, mock_db):
        """Test cleanup of old completed jobs."""
        # Setup
        old_date = datetime.utcnow() - timedelta(days=8)  # Older than 7 days
        old_job = Job(
            id="old_job",
            user_id="test_user",
            file_id="test_file",
            file_name="old.mp3",
            status=JobStatus.COMPLETED,
            completed_at=old_date
        )
        mock_db.list_jobs.return_value = [old_job]
        
        # Run cleanup
        await job_manager.cleanup_old_jobs(max_age_days=7)
        
        # Verify job was deleted
        mock_db.delete_job.assert_called_once_with("old_job")

    @pytest.mark.parametrize("current_status,new_status,should_allow", [
        (JobStatus.PENDING, JobStatus.PROCESSING, True),
        (JobStatus.PROCESSING, JobStatus.COMPLETED, True),
        (JobStatus.PROCESSING, JobStatus.FAILED, True),
        (JobStatus.COMPLETED, JobStatus.PROCESSING, False),
        (JobStatus.FAILED, JobStatus.COMPLETED, False),
    ])
    async def test_status_transitions(
        self, job_manager, mock_db, current_status, new_status, should_allow
    ):
        """Test valid and invalid status transitions."""
        # Setup
        job_id = "test_job"
        job = Job(
            id=job_id,
            user_id="test_user",
            file_id="test_file",
            file_name="test.mp3",
            status=current_status
        )
        mock_db.get_job.return_value = job
        
        if should_allow:
            # Should succeed
            await job_manager.update_job_status(job_id, new_status)
            mock_db.update_job.assert_called_once()
        else:
            # Should raise error
            with pytest.raises(ValueError):
                await job_manager.update_job_status(job_id, new_status)

    async def test_concurrent_jobs(self, job_manager, mock_db):
        """Test handling of concurrent jobs."""
        # Setup multiple pending jobs
        jobs = [
            Job(
                id=f"job{i}",
                user_id="test_user",
                file_id=f"file{i}",
                file_name=f"test{i}.mp3",
                status=JobStatus.PENDING,
                priority=JobPriority.NORMAL
            )
            for i in range(5)
        ]
        mock_db.list_jobs.return_value = jobs
        
        # Get multiple jobs
        next_jobs = []
        for _ in range(3):
            job = await job_manager.get_next_job()
            if job:
                next_jobs.append(job)
                # Simulate job starting
                await job_manager.update_job_status(
                    job.id,
                    JobStatus.PROCESSING
                )
        
        # Verify unique jobs were returned
        job_ids = [job.id for job in next_jobs]
        assert len(job_ids) == len(set(job_ids))  # No duplicates
