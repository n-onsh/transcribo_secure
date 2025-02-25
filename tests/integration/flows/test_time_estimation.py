import pytest
import asyncio
from datetime import datetime, timedelta
from backend.src.models.job import Job, JobStatus, JobPriority, TranscriptionOptions
from backend.src.services.database import DatabaseService
from backend.src.services.job_manager import JobManager
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
async def job_manager(db, storage):
    """Create job manager"""
    manager = JobManager(storage=storage, db=db)
    await manager.start()
    yield manager
    await manager.stop()

@pytest.mark.asyncio
async def test_job_time_estimation_flow(job_manager, db):
    """Test complete job time estimation flow"""
    # Create test audio data
    audio_data = b"test" * 1024  # 4KB test file
    file_name = "test.mp3"
    
    # Create job with German language
    job = await job_manager.create_job(
        user_id="test_user",
        file_data=audio_data,
        file_name=file_name,
        options=TranscriptionOptions(language="de")
    )
    
    # Verify initial estimates
    assert job.estimated_time is not None
    assert job.estimated_range is not None
    assert job.estimate_confidence is not None
    assert job.estimated_time > 0
    assert job.estimated_range[0] <= job.estimated_range[1]
    assert 0 <= job.estimate_confidence <= 1

    # Complete several jobs to build statistics
    for i in range(5):
        job = await job_manager.create_job(
            user_id="test_user",
            file_data=audio_data,
            file_name=f"test_{i}.mp3",
            options=TranscriptionOptions(language="de")
        )
        
        # Simulate processing
        job.status = JobStatus.PROCESSING
        job.progress = 50.0
        await db.update_job(job.id, job)
        
        # Simulate completion
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.utcnow()
        await db.update_job(job.id, job)

    # Get performance metrics
    metrics = await db.get_performance_metrics()
    assert "de" in metrics
    assert metrics["de"]["total_jobs"] >= 5
    assert metrics["de"]["avg_processing_time"] > 0

    # Create new job and verify estimates improved
    new_job = await job_manager.create_job(
        user_id="test_user",
        file_data=audio_data,
        file_name="test_new.mp3",
        options=TranscriptionOptions(language="de")
    )
    
    # Verify estimates are based on historical data
    assert new_job.estimate_confidence > 0.5  # Higher confidence with more data
    assert new_job.estimated_time > 0
    assert new_job.estimated_range[0] <= new_job.estimated_range[1]

@pytest.mark.asyncio
async def test_language_specific_estimates(job_manager, db):
    """Test language-specific time estimates"""
    audio_data = b"test" * 1024
    
    # Create jobs for different languages
    languages = ["de", "en", "fr"]
    jobs_per_language = 5
    
    for lang in languages:
        for i in range(jobs_per_language):
            job = await job_manager.create_job(
                user_id="test_user",
                file_data=audio_data,
                file_name=f"{lang}_{i}.mp3",
                options=TranscriptionOptions(language=lang)
            )
            
            # Simulate different processing times for each language
            await asyncio.sleep(0.1)  # Small delay
            
            # Complete job
            job.status = JobStatus.COMPLETED
            job.progress = 100.0
            job.completed_at = datetime.utcnow()
            await db.update_job(job.id, job)
    
    # Get metrics for each language
    metrics = await db.get_performance_metrics()
    
    # Verify language-specific stats
    for lang in languages:
        assert lang in metrics
        assert metrics[lang]["total_jobs"] >= jobs_per_language
        assert metrics[lang]["avg_processing_time"] > 0

    # Compare estimates for different languages
    estimates = {}
    for lang in languages:
        estimate = await db.estimate_processing_time(60.0, lang)  # 1 minute audio
        estimates[lang] = estimate
    
    # Verify each language has unique estimates
    assert len(set(e["estimated_time"] for e in estimates.values())) > 1

@pytest.mark.asyncio
async def test_estimate_confidence_levels(job_manager, db):
    """Test confidence level calculation"""
    audio_data = b"test" * 1024
    
    # Get initial estimate with no history
    initial_job = await job_manager.create_job(
        user_id="test_user",
        file_data=audio_data,
        file_name="initial.mp3",
        options=TranscriptionOptions(language="de")
    )
    initial_confidence = initial_job.estimate_confidence
    
    # Complete several jobs
    for i in range(10):
        job = await job_manager.create_job(
            user_id="test_user",
            file_data=audio_data,
            file_name=f"confidence_{i}.mp3",
            options=TranscriptionOptions(language="de")
        )
        
        # Complete job
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.utcnow()
        await db.update_job(job.id, job)
    
    # Get new estimate
    final_job = await job_manager.create_job(
        user_id="test_user",
        file_data=audio_data,
        file_name="final.mp3",
        options=TranscriptionOptions(language="de")
    )
    
    # Verify confidence increased
    assert final_job.estimate_confidence > initial_confidence

@pytest.mark.asyncio
async def test_estimate_range_accuracy(job_manager, db):
    """Test accuracy of estimated time ranges"""
    audio_data = b"test" * 1024
    completed_jobs = []
    
    # Complete several jobs
    for i in range(10):
        job = await job_manager.create_job(
            user_id="test_user",
            file_data=audio_data,
            file_name=f"range_{i}.mp3",
            options=TranscriptionOptions(language="de")
        )
        
        # Record estimate
        estimate = job.estimated_range
        
        # Complete job with random delay
        await asyncio.sleep(0.1 * (i % 3))  # Vary processing time
        job.status = JobStatus.COMPLETED
        job.progress = 100.0
        job.completed_at = datetime.utcnow()
        await db.update_job(job.id, job)
        
        # Calculate actual duration
        actual_duration = (job.completed_at - job.created_at).total_seconds()
        completed_jobs.append((estimate, actual_duration))
    
    # Verify most actual durations fall within estimated ranges
    in_range_count = sum(
        1 for estimate, actual in completed_jobs
        if estimate[0] <= actual <= estimate[1]
    )
    
    assert in_range_count >= len(completed_jobs) * 0.8  # At least 80% accurate
