from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from uuid import uuid4
from ..services.database import DatabaseService
from ..services.storage import StorageService
from ..models.file import FileMetadata
from ..models.job import TranscriptionOptions
from datetime import datetime
from typing import Optional, List

router = APIRouter()

async def get_services():
    """Dependency to get database and storage services"""
    db = DatabaseService()
    storage = StorageService()
    try:
        yield {"db": db, "storage": storage}
    finally:
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
        # Store file
        file_metadata = await services["storage"].store_file(
            file_id=uuid4(),
            file_data=file.file,
            file_name=file.filename,
            file_type='input'
        )
        
        # Create transcription options
        options = TranscriptionOptions(
            vocabulary=vocabulary,
            generate_srt=True
        )
        
        # Create transcription job
        job = await services["job_processor"].create_transcription_job(
            file_id=file_metadata.file_id,
            user_id=user_id,
            file_name=file.filename,
            options=options
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