"""File routes."""

import os
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from typing import List, Optional, Dict, Any
from ..utils.logging import log_error
from ..utils.hash_verification import calculate_data_hash, verify_file_hash, HashVerificationError
from ..models.file import FileResponse
from ..models.job import TranscriptionOptions
from ..services.interfaces import StorageInterface, JobManagerInterface
from ..services.provider import service_provider
from ..services.zip_handler import ZipHandlerService
from ..utils.exceptions import ResourceNotFoundError, AuthorizationError
from ..utils.metrics import track_time, track_errors, DB_OPERATION_DURATION

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

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
    user_id: str = None  # Set by auth middleware
):
    """Upload a file for transcription with progress tracking"""
    try:
        # Get required services
        storage = service_provider.get(StorageInterface)
        job_manager = service_provider.get(JobManagerInterface)
        zip_handler = service_provider.get(ZipHandlerService)
        
        if not storage or not job_manager or not zip_handler:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Read file data and calculate hash
        file_data = await file.read()
        hash_algorithm = "sha256"
        file_hash = calculate_data_hash(file_data)

        # Save uploaded file temporarily
        temp_path = os.path.join("/tmp", file.filename)
        with open(temp_path, "wb") as f:
            f.write(file_data)

        # Verify hash after writing
        if not verify_file_hash(temp_path, file_hash, hash_algorithm):
            # If verification fails, delete file and raise error
            os.remove(temp_path)
            raise HashVerificationError("File hash verification failed after storage")

        # Check if it's a ZIP file
        if zip_handler.is_zip_file(file.filename):
            # Process ZIP file
            try:
                zip_result = await zip_handler.process_zip_file(temp_path, str(user_id))
                file_path = zip_result["combined_file"]
                metadata = {
                    "original_files": zip_result["original_files"],
                    "is_combined": zip_result["is_combined"]
                }
            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(e)
                )
        else:
            # Validate single file type
            if not zip_handler.is_supported_audio_file(file.filename):
                allowed_types = zip_handler.supported_audio_extensions
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)} or ZIP"
                )
            file_path = temp_path
            metadata = {"is_combined": False}

        # Create transcription options
        options = TranscriptionOptions(
            language=language,
            vocabulary=vocabulary.split(",") if vocabulary else []
        )

        # Create transcription job
        try:
            with open(file_path, "rb") as f:
                job = await job_manager.create_job(
                    user_id=user_id,
                    file_data=f,
                    file_name=file.filename,
                    options=options,
                    metadata=metadata
                )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        finally:
            # Clean up temporary files
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if file_path != temp_path and os.path.exists(file_path):
                os.remove(file_path)

        return FileResponse(
            id=job.id,
            name=file.filename,
            status=job.status,
            created_at=job.created_at,
            progress=job.progress,
            language=job.options.language,
            supported_languages=job.options.supported_languages,
            hash=file_hash,
            hash_algorithm=hash_algorithm
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
        log_error("Upload failed", {
            "error": str(e),
            "file_name": file.filename,
            "user_id": user_id
        })
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
    offset: Optional[int] = 0,
    language: Optional[str] = None
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

        # Get jobs with language filter
        jobs = await job_manager.list_jobs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            language=language
        )

        return [
            FileResponse(
                id=job.id,
                name=job.file_name,
                status=job.status,
                created_at=job.created_at,
                completed_at=job.completed_at,
                error=job.error,
                language=job.options.language,
                supported_languages=job.options.supported_languages
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
