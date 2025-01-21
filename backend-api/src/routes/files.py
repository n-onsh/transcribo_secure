from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from uuid import uuid4
from ..services.database import DatabaseService
from ..services.storage import StorageService
from ..models.file import FileMetadata
from datetime import datetime

router = APIRouter()

async def get_services():
    """Dependency to get database and storage services"""
    db = DatabaseService()
    storage = StorageService()
    try:
        yield {"db": db, "storage": storage}
    finally:
        await db.close()  # Close database connection when done

@router.post("/files/", response_model=FileMetadata)
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = "test_user",  # We'll implement proper auth later
    services: dict = Depends(get_services)
):
    """
    Upload a file with encryption:
    1. Generate unique file ID
    2. Store encrypted file in MinIO
    3. Store metadata in PostgreSQL
    4. Return file metadata to client
    """
    file_id = uuid4()
    try:
        # Store encrypted file
        size = await services["storage"].store_file(
            file_id=file_id,
            file_data=file.file,
            file_name=file.filename,
            file_type='input'
        )
        
        # Create metadata record
        metadata = FileMetadata(
            file_id=file_id,
            user_id=user_id,
            file_name=file.filename,
            file_type="input",
            created_at=datetime.utcnow(),
            size_bytes=size,
            content_type=file.content_type
        )
        
        # Store in database
        await services["db"].create_file(metadata)
        
        return metadata
        
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