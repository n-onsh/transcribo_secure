"""ZIP file upload and processing routes."""

import os
import tempfile
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from opentelemetry import trace, logs
from opentelemetry.logs import Severity

from ..models.job import Job
from ..services.job_manager import JobManager
from ..services.storage import StorageService
from ..services.zip_handler import ZipHandler
from ..utils.metrics import (
    API_REQUEST_TIME,
    API_ERROR_COUNT,
    API_REQUEST_SIZE,
    track_time,
    track_errors
)

router = APIRouter()
logger = logs.get_logger(__name__)
tracer = trace.get_tracer(__name__)

@router.post("/upload")
@track_time("zip_upload_duration", {"endpoint": "/zip/upload"})
@track_errors("zip_upload_errors", {"endpoint": "/zip/upload"})
async def upload_zip(
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    job_manager: JobManager = Depends(),
    storage: StorageService = Depends(),
    zip_handler: ZipHandler = Depends()
) -> List[Job]:
    """Upload and process ZIP file."""
    try:
        # Track request size
        API_REQUEST_SIZE.record(
            file.size,
            {"endpoint": "/zip/upload"}
        )
        
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Validate ZIP
            valid, error = await zip_handler.validate_zip(temp_path)
            if not valid:
                raise HTTPException(400, error)
            
            # Process ZIP
            file_id = UUID(int=hash(file.filename))
            owner_id = UUID(int=hash(file.filename))  # TODO: Get from auth
            
            jobs = []
            async for filename, progress in zip_handler.extract_zip(
                file_id=file_id,
                owner_id=owner_id,
                file_path=temp_path,
                language=language
            ):
                logger.emit(
                    "Processing ZIP file",
                    severity=Severity.INFO,
                    attributes={
                        "filename": filename,
                        "progress": progress
                    }
                )
            
            # Get created jobs
            async with job_manager.db.pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT * FROM jobs
                    WHERE owner_id = $1
                    AND created_at >= NOW() - INTERVAL '5 minutes'
                    ORDER BY created_at ASC
                """, str(owner_id))
                
                jobs = [Job.parse_obj(row) for row in rows]
            
            return jobs
            
        finally:
            # Cleanup temp file
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.emit(
                    "Failed to remove temp file",
                    severity=Severity.WARNING,
                    attributes={
                        "error": str(e),
                        "path": temp_path
                    }
                )
                
    except HTTPException:
        raise
    except Exception as e:
        API_ERROR_COUNT.inc({
            "endpoint": "/zip/upload",
            "error_type": type(e).__name__
        })
        logger.emit(
            "ZIP upload failed",
            severity=Severity.ERROR,
            attributes={"error": str(e)}
        )
        raise HTTPException(500, "Failed to process ZIP file")

@router.get("/progress/{file_id}")
@track_time("zip_progress_duration", {"endpoint": "/zip/progress"})
@track_errors("zip_progress_errors", {"endpoint": "/zip/progress"})
async def get_progress(
    file_id: UUID,
    zip_handler: ZipHandler = Depends()
) -> dict:
    """Get ZIP extraction progress."""
    try:
        progress = await zip_handler.get_extraction_progress(file_id)
        return {
            "file_id": str(file_id),
            "progress": progress
        }
    except Exception as e:
        API_ERROR_COUNT.inc({
            "endpoint": "/zip/progress",
            "error_type": type(e).__name__
        })
        logger.emit(
            "Failed to get ZIP progress",
            severity=Severity.ERROR,
            attributes={
                "error": str(e),
                "file_id": str(file_id)
            }
        )
        raise HTTPException(500, "Failed to get progress")

@router.delete("/{file_id}")
@track_time("zip_cancel_duration", {"endpoint": "/zip/cancel"})
@track_errors("zip_cancel_errors", {"endpoint": "/zip/cancel"})
async def cancel_extraction(
    file_id: UUID,
    zip_handler: ZipHandler = Depends()
) -> dict:
    """Cancel ZIP extraction."""
    try:
        await zip_handler.cancel_extraction(file_id)
        return {
            "file_id": str(file_id),
            "status": "cancelled"
        }
    except Exception as e:
        API_ERROR_COUNT.inc({
            "endpoint": "/zip/cancel",
            "error_type": type(e).__name__
        })
        logger.emit(
            "Failed to cancel ZIP extraction",
            severity=Severity.ERROR,
            attributes={
                "error": str(e),
                "file_id": str(file_id)
            }
        )
        raise HTTPException(500, "Failed to cancel extraction")
