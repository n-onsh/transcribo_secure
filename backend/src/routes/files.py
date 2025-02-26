"""File routes."""

import os
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Depends, status
from typing import List, Optional, Dict, Any, cast
from datetime import datetime
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
    TranscriboError,
    FileError
)
from ..types import (
    ErrorContext,
    FileID,
    UserID,
    FileMetadata,
    FileUploadResult,
    FileOptions,
    ZipProcessingResult
)
from ..utils.route_utils import (
    route_handler,
    map_to_response
)
from ..utils.dependencies import (
    JobManagerDep,
    StorageServiceDep,
    ZipHandlerDep
)

router = APIRouter(
    prefix="/files",
    tags=["files"]
)

async def _handle_file_upload(
    file: UploadFile,
    temp_dir: Path,
    zip_handler: ZipHandlerService,
    user_id: UserID
) -> FileUploadResult:
    """Handle file upload and validation.
    
    Args:
        file: Uploaded file
        temp_dir: Temporary directory for file processing
        zip_handler: ZIP handler service
        user_id: User ID for tracking
        
    Returns:
        File upload result
        
    Raises:
        ValidationError: If file validation fails
        FileError: If file processing fails
    """
    try:
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
                error_context: ErrorContext = {
                    "operation": "verify_hash",
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "file_name": file.filename,
                        "hash": file_hash
                    }
                }
                raise HashVerificationError(
                    "File hash verification failed after storage",
                    details=error_context
                )

            # Check if it's a ZIP file
            if zip_handler.is_zip_file(file.filename):
                # Process ZIP file
                zip_result = await zip_handler.process_zip_file(str(temp_path), user_id)
                file_path = Path(zip_result["combined_file"])
                metadata: FileMetadata = {
                    "name": file.filename,
                    "size": len(file_data),
                    "type": "zip",
                    "original_files": zip_result["original_files"],
                    "is_combined": zip_result["is_combined"],
                    "hash": file_hash,
                    "hash_algorithm": hash_algorithm
                }
            else:
                # Validate single file type
                if not zip_handler.is_supported_audio_file(file.filename):
                    allowed_types = zip_handler.supported_audio_extensions
                    error_context: ErrorContext = {
                        "operation": "validate_file_type",
                        "timestamp": datetime.utcnow(),
                        "details": {
                            "file_name": file.filename,
                            "allowed_types": allowed_types
                        }
                    }
                    raise ValidationError(
                        f"Invalid file type. Allowed types: {', '.join(allowed_types)} or ZIP",
                        details=error_context
                    )
                file_path = temp_path
                metadata = {
                    "name": file.filename,
                    "size": len(file_data),
                    "type": os.path.splitext(file.filename)[1][1:],
                    "is_combined": False,
                    "hash": file_hash,
                    "hash_algorithm": hash_algorithm
                }

            return {
                "file_path": str(file_path),
                "metadata": metadata
            }

        except Exception:
            # Clean up on error
            if temp_path.exists():
                temp_path.unlink()
            raise

    except (ValidationError, HashVerificationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "handle_file_upload",
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "file_name": file.filename
            }
        }
        raise FileError("Failed to process file upload", details=error_context)

@router.post(
    "/upload",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload File",
    description="Upload an audio/video file or ZIP containing audio/video files for transcription"
)
@route_handler("upload_file", FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    language: Optional[str] = None,
    vocabulary: Optional[str] = None,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep),
    storage: StorageService = Depends(StorageServiceDep),
    zip_handler: ZipHandlerService = Depends(ZipHandlerDep)
) -> FileResponse:
    """Upload a file for transcription with progress tracking.
    
    Args:
        file: File to upload
        language: Optional language for transcription
        vocabulary: Optional comma-separated vocabulary list
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        storage: Storage service
        zip_handler: ZIP handler service
        
    Returns:
        File response
        
    Raises:
        ValidationError: If file validation fails
        FileError: If file processing fails
        TranscriboError: If job creation fails
    """
    temp_dir = Path(storage.settings.get('temp_dir', '/tmp'))
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Handle file upload
        upload_result = await _handle_file_upload(
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
            with open(upload_result["file_path"], "rb") as f:
                job = await job_manager.create_job(
                    user_id=user_id,
                    file_data=f,
                    file_name=file.filename,
                    options=options,
                    metadata=upload_result["metadata"]
                )
                
            log_info(f"Created job {job.id} for file {file.filename}")
            return map_to_response(job, FileResponse)
            
        finally:
            # Clean up temporary files
            if os.path.exists(upload_result["file_path"]):
                os.unlink(upload_result["file_path"])
            
    except (ValidationError, FileError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "upload_file",
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "file_name": file.filename,
                "user_id": user_id
            }
        }
        log_error("Upload failed", error_context)
        raise TranscriboError("Failed to process upload", details=error_context)

@router.get(
    "/{file_id}",
    response_model=FileResponse,
    summary="Get File",
    description="Get file information"
)
@route_handler("get_file", FileResponse)
async def get_file(
    file_id: FileID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> FileResponse:
    """Get file information.
    
    Args:
        file_id: File ID to get
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        
    Returns:
        File response
        
    Raises:
        ResourceNotFoundError: If file not found
        AuthorizationError: If user not authorized
        TranscriboError: If operation fails
    """
    try:
        job = await job_manager.get_job_status(file_id)
        
        # Check authorization
        if user_id and job.get('owner_id') != user_id:
            error_context: ErrorContext = {
                "operation": "get_file",
                "resource_id": file_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": "Not authorized"}
            }
            raise AuthorizationError("Not authorized to access this file", details=error_context)
            
        return map_to_response(job, FileResponse)
        
    except (ResourceNotFoundError, AuthorizationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "get_file",
            "resource_id": file_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to get file", details=error_context)

@router.get(
    "/",
    response_model=List[FileResponse],
    summary="List Files",
    description="List files for the authenticated user"
)
@route_handler("list_files", List[FileResponse])
async def list_files(
    user_id: Optional[UserID] = None,  # Set by auth middleware
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    language: Optional[str] = None,
    job_manager: JobManager = Depends(JobManagerDep)
) -> List[FileResponse]:
    """List files for a user.
    
    Args:
        user_id: Optional user ID for filtering
        limit: Maximum number of files to return
        offset: Number of files to skip
        language: Optional language filter
        job_manager: Job manager service
        
    Returns:
        List of file responses
        
    Raises:
        ValidationError: If parameters invalid
        TranscriboError: If operation fails
    """
    try:
        # Validate parameters
        if limit < 0 or offset < 0:
            error_context: ErrorContext = {
                "operation": "list_files",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": "Invalid parameters",
                    "limit": limit,
                    "offset": offset
                }
            }
            raise ValidationError("Invalid pagination parameters", details=error_context)
            
        filters = {
            "user_id": user_id,
            "limit": limit,
            "offset": offset,
            "language": language
        }
        
        jobs = await job_manager.list_jobs(filters)
        return [map_to_response(job, FileResponse) for job in jobs]
        
    except ValidationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "list_files",
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "filters": filters
            }
        }
        raise TranscriboError("Failed to list files", details=error_context)

@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete File",
    description="Delete a file and its associated job"
)
@route_handler("delete_file")
async def delete_file(
    file_id: FileID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> None:
    """Delete a file.
    
    Args:
        file_id: File ID to delete
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        
    Raises:
        ResourceNotFoundError: If file not found
        AuthorizationError: If user not authorized
        TranscriboError: If operation fails
    """
    try:
        # Check authorization
        job = await job_manager.get_job_status(file_id)
        if user_id and job.get('owner_id') != user_id:
            error_context: ErrorContext = {
                "operation": "delete_file",
                "resource_id": file_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": "Not authorized"}
            }
            raise AuthorizationError("Not authorized to delete this file", details=error_context)
            
        await job_manager.delete_job(file_id)
        
    except (ResourceNotFoundError, AuthorizationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "delete_file",
            "resource_id": file_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to delete file", details=error_context)
