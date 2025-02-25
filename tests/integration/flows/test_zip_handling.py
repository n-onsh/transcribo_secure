"""Integration tests for ZIP file handling."""

import asyncio
import os
import pytest
import zipfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from backend.src.models.file import File
from backend.src.models.job import Job, JobStatus
from backend.src.services.storage import StorageService
from backend.src.services.job_manager import JobManager
from backend.src.services.zip_handler import ZipHandler
from backend.src.services.database import DatabaseService

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
    manager = JobManager(db=db, storage=storage)
    await manager.initialize()
    return manager

@pytest.fixture
async def zip_handler(storage, job_manager):
    """Create ZIP handler"""
    handler = ZipHandler(
        storage=storage,
        job_manager=job_manager,
        max_file_size=10 * 1024 * 1024,  # 10MB for tests
        max_files=10,
        allowed_extensions={'mp3', 'wav'},
        chunk_size=8192,
        extraction_timeout=30
    )
    return handler

@pytest.fixture
def test_files(tmp_path):
    """Create test audio files"""
    files = []
    for i in range(3):
        file_path = tmp_path / f"test_{i}.mp3"
        # Create 1MB test file
        with open(file_path, 'wb') as f:
            f.write(os.urandom(1024 * 1024))
        files.append(file_path)
    return files

@pytest.fixture
def test_zip(tmp_path, test_files):
    """Create test ZIP file"""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zip_file:
        for file_path in test_files:
            zip_file.write(file_path, file_path.name)
    return zip_path

@pytest.mark.asyncio
async def test_complete_zip_flow(zip_handler, test_zip, db):
    """Test complete ZIP processing flow"""
    file_id = uuid4()
    owner_id = uuid4()
    
    # Validate ZIP
    valid, error = await zip_handler.validate_zip(test_zip)
    assert valid
    assert error is None
    
    # Extract files
    filenames = []
    progress_values = []
    
    async for filename, progress in zip_handler.extract_zip(
        file_id=file_id,
        owner_id=owner_id,
        file_path=str(test_zip),
        language="en"
    ):
        filenames.append(filename)
        progress_values.append(progress)
    
    # Verify files processed
    assert len(filenames) == 3
    assert all(f.endswith('.mp3') for f in filenames)
    
    # Verify progress
    assert len(progress_values) == 3
    assert progress_values[-1] == 100.0
    
    # Verify files in storage
    for filename in filenames:
        file_exists = await zip_handler.storage.file_exists(filename)
        assert file_exists
    
    # Verify jobs created
    async with db.pool.acquire() as conn:
        jobs = await conn.fetch("""
            SELECT * FROM jobs
            WHERE owner_id = $1
            ORDER BY created_at ASC
        """, str(owner_id))
        
        assert len(jobs) == 3
        for job in jobs:
            assert job['status'] == JobStatus.PENDING.value
            assert job['file_name'] in filenames

@pytest.mark.asyncio
async def test_concurrent_zip_processing(zip_handler, test_zip, db):
    """Test processing multiple ZIP files concurrently"""
    file_ids = [uuid4() for _ in range(3)]
    owner_id = uuid4()
    
    # Start multiple extractions
    tasks = []
    for file_id in file_ids:
        task = asyncio.create_task(
            process_zip(
                zip_handler=zip_handler,
                file_id=file_id,
                owner_id=owner_id,
                zip_path=test_zip
            )
        )
        tasks.append(task)
    
    # Wait for all to complete
    results = await asyncio.gather(*tasks)
    
    # Verify all succeeded
    assert all(results)
    
    # Verify jobs created
    async with db.pool.acquire() as conn:
        jobs = await conn.fetch("""
            SELECT * FROM jobs
            WHERE owner_id = $1
        """, str(owner_id))
        
        assert len(jobs) == 9  # 3 files * 3 extractions

@pytest.mark.asyncio
async def test_zip_error_recovery(zip_handler, test_zip, db, tmp_path):
    """Test error recovery during ZIP processing"""
    file_id = uuid4()
    owner_id = uuid4()
    
    # Create corrupted ZIP
    corrupted_zip = tmp_path / "corrupted.zip"
    with open(test_zip, 'rb') as src, open(corrupted_zip, 'wb') as dst:
        content = src.read()
        # Corrupt middle portion
        middle = len(content) // 2
        content = content[:middle] + b'garbage' + content[middle+7:]
        dst.write(content)
    
    # Attempt extraction
    try:
        async for _ in zip_handler.extract_zip(
            file_id=file_id,
            owner_id=owner_id,
            file_path=str(corrupted_zip)
        ):
            pass
    except Exception:
        pass
    
    # Verify partial cleanup
    assert not os.path.exists(corrupted_zip)
    
    # Check no orphaned jobs
    async with db.pool.acquire() as conn:
        jobs = await conn.fetch("""
            SELECT * FROM jobs
            WHERE owner_id = $1
        """, str(owner_id))
        
        assert len(jobs) == 0

@pytest.mark.asyncio
async def test_zip_progress_tracking(zip_handler, test_zip):
    """Test ZIP extraction progress tracking"""
    file_id = uuid4()
    owner_id = uuid4()
    
    # Track progress
    progress_updates = []
    async for _, progress in zip_handler.extract_zip(
        file_id=file_id,
        owner_id=owner_id,
        file_path=str(test_zip)
    ):
        progress_updates.append(progress)
        
        # Check progress is available
        current = await zip_handler.get_extraction_progress(file_id)
        if current is not None:
            assert current <= progress
    
    # Verify progress sequence
    assert len(progress_updates) == 3
    assert progress_updates == [33.33333333333333, 66.66666666666666, 100.0]
    
    # Verify progress cleared after completion
    final = await zip_handler.get_extraction_progress(file_id)
    assert final is None

@pytest.mark.asyncio
async def test_zip_cancellation_cleanup(zip_handler, test_zip, db):
    """Test cleanup after ZIP extraction cancellation"""
    file_id = uuid4()
    owner_id = uuid4()
    
    # Start extraction
    extraction = asyncio.create_task(
        process_zip(
            zip_handler=zip_handler,
            file_id=file_id,
            owner_id=owner_id,
            zip_path=test_zip
        )
    )
    
    # Wait briefly then cancel
    await asyncio.sleep(0.1)
    await zip_handler.cancel_extraction(file_id)
    
    try:
        await extraction
    except asyncio.CancelledError:
        pass
    
    # Verify cleanup
    assert not os.path.exists(test_zip)
    
    # Verify no orphaned jobs
    async with db.pool.acquire() as conn:
        jobs = await conn.fetch("""
            SELECT * FROM jobs
            WHERE owner_id = $1
        """, str(owner_id))
        
        assert len(jobs) == 0

async def process_zip(
    zip_handler: ZipHandler,
    file_id: UUID,
    owner_id: UUID,
    zip_path: str
) -> bool:
    """Helper to process ZIP file"""
    try:
        async for _ in zip_handler.extract_zip(
            file_id=file_id,
            owner_id=owner_id,
            file_path=str(zip_path)
        ):
            pass
        return True
    except Exception:
        return False
