from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from uuid import uuid4
from ..services.database import DatabaseService
from ..services.storage import StorageService
from ..services.job_manager import JobManager
from ..models.file import FileMetadata
from ..models.job import TranscriptionOptions, JobPriority
from datetime import datetime
from typing import Optional, List

router = APIRouter()

async def get_services():
    """Dependency to get required services"""
    db = DatabaseService()
    storage = StorageService()
    job_manager = JobManager(storage=storage, db=db)
    try:
        yield {"db": db, "storage": storage, "job_manager": job_manager}
    finally:
        await job_manager.stop()
        await db.close()  # Close database connection when done

@router.post("/files/")
async def upload_file(
    file: UploadFile = File(...),
    vocabulary: Optional[List[str]] = None,
    user_id: str = "test_user",  # We'll implement proper auth later
    services: dict = Depends(get_services)
):
    """
    Upload a file and create a transcription job
    """
    try:
        # Read file data once
        file_data = await file.read()
        file_id = uuid4()
        
        # Store file
        file_metadata = await services["storage"].store_file(
            file_id=file_id,
            file_data=file_data,
            file_name=file.filename,
            file_type='input'
        )
        
        # Create transcription job with the same file data
        job = await services["job_manager"].create_job(
            user_id=user_id,
            file_data=file_data,
            file_name=file.filename,
            priority=JobPriority.NORMAL
        )
        
        return {
            "file": file_metadata,
            "job": job
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    services: dict = Depends(get_services)
):
    """
    Retrieve a file:
    1. Get metadata from database
    2. Get encrypted file from MinIO
    3. Decrypt and return file
    """
    try:
        # Get metadata
        metadata = await services["db"].get_file(file_id)
        if not metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Get decrypted file
        file_data = await services["storage"].retrieve_file(
            file_id=metadata.file_id,
            file_name=metadata.file_name,
            file_type=metadata.file_type
        )
        
        if not file_data:
            raise HTTPException(status_code=404, detail="File not found in storage")
            
        return JSONResponse({
            "metadata": metadata,
            "file_found": True
        })
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
