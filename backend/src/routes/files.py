"""File routes."""

import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, status
from typing import List, Optional, Dict, Any
from ..utils.logging import log_error, log_info
from ..utils.hash_verification import calculate_data_hash, verify_file_hash, HashVerificationError
from ..models.file import FileResponse
from ..models.job import TranscriptionOptions
from ..services.job_manager import JobManager
from ..services.storage import StorageService
from ..services.zip_handler import ZipHandlerService
from ..utils.exceptions import (
    ResourceNotFoundError,
    AuthorizationError,
    ValidationError,
    TranscriboError
)
from ..utils.metrics import track_time, track_errors, DB_OPERATION_DURATION
from ..utils.dependencies import (
    JobManager as JobManagerDep,
    StorageService as StorageServiceDep,
    ZipHandlerService as ZipHandlerDep
)

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

def _map_job_to_file_response(job) -> FileResponse:
    """Map job model to file response model."""
    return FileResponse(
        id=job.id,
        name=job.file_name,
        status=job.status,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error=job.error,
        progress=job.progress,
        language=job.options.language if job.options else None,
        supported_languages=job.options.supported_languages if job.options else None,
        is_zip=job.is_zip,
        zip_progress=job.zip_progress,
        sub_jobs=job.sub_jobs,
        parent_job_id=job.parent_job_id
    )

async def _handle_file_upload(
    file: UploadFile,
    temp_dir: Path,
    zip_handler: ZipHandlerService,
    user_id: str
) -> tuple[Path, Dict[str, Any]]:
    """Handle file upload and validation."""
    # Read file data and calculate hash
    file_data = await file.read()
    hash_algorithm = "sha256"
    file_hash = calculate_data_hash(file_data)

    # Save uploaded file temporarily
    temp_path = temp_dir / file.filename
    temp_path.write_bytes(file_data)

    try:
        # Verify hash after writing
        if not verify_file_hash(str(temp_path), file_hash, hash_algorithm):
            raise HashVerificationError("File hash verification failed after storage")

        # Check if it's a ZIP file
        if zip_handler.is_zip_file(file.filename):
            # Process ZIP file
            zip_result = await zip_handler.process_zip_file(str(temp_path), str(user_id))
            file_path = Path(zip_result["combined_file"])
            metadata = {
                "original_files": zip_result["original_files"],
                "is_combined": zip_result["is_combined"],
                "hash": file_hash,
                "hash_algorithm": hash_algorithm
            }
        else:
            # Validate single file type
            if not zip_handler.is_supported_audio_file(file.filename):
                allowed_types = zip_handler.supported_audio_extensions
                raise ValidationError(
                    f"Invalid file type. Allowed types: {', '.join(allowed_types)} or ZIP"
                )
            file_path = temp_path
            metadata = {
                "is_combined": False,
                "hash": file_hash,
                "hash_algorithm": hash_algorithm
            }

        return file_path, metadata

    except Exception:
        # Clean up on error
        if temp_path.exists():
            temp_path.unlink()
        raise

@router.post(
    "/upload",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload File",
    description="Upload an audio/video file or ZIP containing audio/video files for transcription"
)
@track_time(DB_OPERATION_DURATION, {"operation": "upload_file"})
async def upload_file(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    vocabulary: Optional[str] = None,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep),
    storage: StorageService = Depends(StorageServiceDep),
    zip_handler: ZipHandlerService = Depends(ZipHandlerDep)
):
    """Upload a file for transcription with progress tracking"""
    temp_dir = Path(storage.settings.get('temp_dir', '/tmp'))
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Handle file upload
        file_path, metadata = await _handle_file_upload(
            file,
            temp_dir,
            zip_handler,
            user_id
        )
        
        try:
            # Create transcription options
            options = TranscriptionOptions(
                language=language,
                vocabulary=vocabulary.split(",") if vocabulary else []
            )

            # Create transcription job
            with open(file_path, "rb") as f:
                job = await job_manager.create_job(
                    user_id=user_id,
                    file_data=f,
                    file_name=file.filename,
                    options=options,
                    metadata=metadata
                )
                
            log_info(f"Created job {job.id} for file {file.filename}")
            return _map_job_to_file_response(job)
            
        finally:
            # Clean up temporary files
            if file_path.exists():
                file_path.unlink()
            
    except TranscriboError:
        # Let error middleware handle TranscriboError
        raise
    except Exception as e:
        log_error("Upload failed", {
            "error": str(e),
            "file_name": file.filename,
            "user_id": user_id
        })
        raise TranscriboError(
            "Failed to process upload",
            details={
                "file_name": file.filename,
                "error": str(e)
            }
        )

@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="Get File",
    description="Get file information"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_file"})
async def get_file(
    file_id: str,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
):
    """Get file information"""
    job = await job_manager.get_job(file_id, user_id)
    return _map_job_to_file_response(job)

@router.get(
    "/",
    response_model=List[FileResponse],
    summary="List Files",
    description="List files for the authenticated user"
)
@track_time(DB_OPERATION_DURATION, {"operation": "list_files"})
async def list_files(
    user_id: str = None,  # Set by auth middleware
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    language: Optional[str] = None,
    job_manager: JobManager = Depends(JobManagerDep)
):
    """List files for a user"""
    jobs = await job_manager.list_jobs(
        user_id=user_id,
        limit=limit,
        offset=offset,
        language=language
    )
    return [_map_job_to_file_response(job) for job in jobs]

@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete File",
    description="Delete a file and its associated job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "delete_file"})
async def delete_file(
    file_id: str,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
):
    """Delete a file"""
    await job_manager.delete_job(file_id, user_id)
