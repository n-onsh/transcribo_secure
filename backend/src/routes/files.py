import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from typing import List, Optional, Dict, Any
from ..models.file import FileResponse
from ..services.interfaces import StorageInterface, JobManagerInterface
from ..services.provider import service_provider
from ..utils.exceptions import ResourceNotFoundError, AuthorizationError
from ..utils.metrics import track_time, track_errors, DB_OPERATION_DURATION

logger = logs.get_logger(__name__)

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

@router.post(
    "/upload",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload File",
    description="Upload an audio/video file for transcription with progress tracking"
)
@track_time(DB_OPERATION_DURATION, {"operation": "upload_file"})
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = None  # Set by auth middleware
):
    """Upload a file for transcription with progress tracking"""
    try:
        # Get required services
        storage = service_provider.get(StorageInterface)
        job_manager = service_provider.get(JobManagerInterface)
        if not storage or not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Validate file type
        allowed_types = {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in allowed_types:
            raise ValueError(f"Invalid file type. Allowed types: {', '.join(allowed_types)}")

        # Create transcription job with streaming upload
        try:
            job = await job_manager.create_job(
                user_id=user_id,
                file_data=file.file,  # Pass file object directly for streaming
                file_name=file.filename
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )

        return FileResponse(
            id=job.id,
            name=file.filename,
            status=job.status,
            created_at=job.created_at,
            progress=job.progress
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except IOError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )
    except Exception as e:
        logger.emit(
            "Upload failed",
            severity=Severity.ERROR,
            attributes={
                "error": str(e),
                "file_name": file.filename,
                "user_id": user_id
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during upload"
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
    user_id: str = None  # Set by auth middleware
):
    """Get file information"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get job
        job = await job_manager.get_job(file_id, user_id)
        if not job:
            raise ResourceNotFoundError("file", file_id)

        return FileResponse(
            id=job.id,
            name=job.file_name,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
            error=job.error
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
    offset: Optional[int] = 0
):
    """List files for a user"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get jobs
        jobs = await job_manager.list_jobs(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        return [
            FileResponse(
                id=job.id,
                name=job.file_name,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
                error=job.error
            )
            for job in jobs
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete File",
    description="Delete a file and its associated job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "delete_file"})
async def delete_file(
    file_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Delete a file"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Delete job (this will also delete associated files)
        await job_manager.delete_job(file_id, user_id)

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
