"""Tests for job pagination."""

import pytest
from datetime import datetime, timedelta
from uuid import UUID
import base64
import json

from backend.src.models.job import Job, JobStatus, TranscriptionOptions
from backend.src.services.job_manager import JobManager
from backend.src.utils.exceptions import ValidationError

@pytest.fixture
def job_manager():
    """Create job manager."""
    return JobManager({})

@pytest.fixture
async def test_jobs(job_manager):
    """Create test jobs."""
    jobs = []
    base_time = datetime.utcnow()
    
    # Create 10 test jobs with different timestamps
    for i in range(10):
        job = Job(
            id=UUID(f"1234567{i}-1234-5678-1234-567812345678"),
            owner_id=UUID("00000000-0000-0000-0000-000000000001"),
            file_name=f"test{i}.wav",
            status=JobStatus.PENDING,
            options=TranscriptionOptions(language="en"),
            metadata={
                "size": 1000,
                "type": "wav"
            },
            created_at=base_time - timedelta(minutes=i)
        )
        await job_manager.job_repository.create(job)
        jobs.append(job)
        
    return jobs

@pytest.mark.asyncio
async def test_list_jobs_no_cursor(job_manager, test_jobs):
    """Test listing jobs without cursor."""
    # Get first page
    jobs, next_cursor, total = await job_manager.list_jobs_with_cursor(
        limit=5,
        sort_field="created_at",
        sort_direction="desc"
    )
    
    assert len(jobs) == 5
    assert total == 10
    assert next_cursor is not None
    
    # Verify order (newest first)
    for i in range(4):
        assert jobs[i]["created_at"] > jobs[i + 1]["created_at"]

@pytest.mark.asyncio
async def test_list_jobs_with_cursor(job_manager, test_jobs):
    """Test listing jobs with cursor."""
    # Get first page
    jobs1, cursor1, total = await job_manager.list_jobs_with_cursor(
        limit=3,
        sort_field="created_at",
        sort_direction="desc"
    )
    
    assert len(jobs1) == 3
    assert cursor1 is not None
    
    # Get second page
    jobs2, cursor2, _ = await job_manager.list_jobs_with_cursor(
        cursor=cursor1,
        limit=3,
        sort_field="created_at",
        sort_direction="desc"
    )
    
    assert len(jobs2) == 3
    assert cursor2 is not None
    
    # Verify no overlap
    job_ids1 = {job["id"] for job in jobs1}
    job_ids2 = {job["id"] for job in jobs2}
    assert not job_ids1.intersection(job_ids2)
    
    # Verify order maintained
    assert jobs1[-1]["created_at"] > jobs2[0]["created_at"]

@pytest.mark.asyncio
async def test_list_jobs_with_filter(job_manager, test_jobs):
    """Test listing jobs with filter."""
    # Add job with different language
    job = Job(
        id=UUID("99999999-1234-5678-1234-567812345678"),
        owner_id=UUID("00000000-0000-0000-0000-000000000001"),
        file_name="test_fr.wav",
        status=JobStatus.PENDING,
        options=TranscriptionOptions(language="fr"),
        metadata={
            "size": 1000,
            "type": "wav"
        },
        created_at=datetime.utcnow()
    )
    await job_manager.job_repository.create(job)
    
    # Get jobs with language filter
    jobs, cursor, total = await job_manager.list_jobs_with_cursor(
        limit=10,
        sort_field="created_at",
        sort_direction="desc",
        filters={"language": "fr"}
    )
    
    assert len(jobs) == 1
    assert total == 1
    assert jobs[0]["options"]["language"] == "fr"

@pytest.mark.asyncio
async def test_list_jobs_invalid_cursor(job_manager, test_jobs):
    """Test listing jobs with invalid cursor."""
    with pytest.raises(ValidationError) as exc:
        await job_manager.list_jobs_with_cursor(
            cursor="invalid",
            limit=5,
            sort_field="created_at",
            sort_direction="desc"
        )
    assert "Invalid cursor format" in str(exc.value)

@pytest.mark.asyncio
async def test_list_jobs_invalid_sort(job_manager, test_jobs):
    """Test listing jobs with invalid sort field."""
    with pytest.raises(ValidationError) as exc:
        await job_manager.list_jobs_with_cursor(
            limit=5,
            sort_field="invalid_field",
            sort_direction="desc"
        )
    assert "Invalid sort field" in str(exc.value)

@pytest.mark.asyncio
async def test_list_jobs_ascending(job_manager, test_jobs):
    """Test listing jobs in ascending order."""
    jobs, cursor, total = await job_manager.list_jobs_with_cursor(
        limit=5,
        sort_field="created_at",
        sort_direction="asc"
    )
    
    assert len(jobs) == 5
    
    # Verify order (oldest first)
    for i in range(4):
        assert jobs[i]["created_at"] < jobs[i + 1]["created_at"]

@pytest.mark.asyncio
async def test_list_jobs_exact_limit(job_manager, test_jobs):
    """Test listing jobs with limit equal to total."""
    jobs, cursor, total = await job_manager.list_jobs_with_cursor(
        limit=10,
        sort_field="created_at",
        sort_direction="desc"
    )
    
    assert len(jobs) == 10
    assert cursor is None  # No more pages

@pytest.mark.asyncio
async def test_cursor_format(job_manager, test_jobs):
    """Test cursor format and content."""
    jobs, cursor, total = await job_manager.list_jobs_with_cursor(
        limit=5,
        sort_field="created_at",
        sort_direction="desc"
    )
    
    # Decode cursor
    cursor_json = base64.b64decode(cursor.encode()).decode()
    cursor_data = json.loads(cursor_json)
    
    # Verify cursor structure
    assert "last_id" in cursor_data
    assert "last_value" in cursor_data
    
    # Verify values
    last_job = jobs[-1]
    assert cursor_data["last_id"] == str(last_job["id"])
    assert cursor_data["last_value"] == last_job["created_at"].isoformat()
