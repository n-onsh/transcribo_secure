"""ZIP file routes."""

import os
import asyncio
import zipfile
from datetime import datetime
from typing import Dict, Optional, List
from fastapi import APIRouter, Depends, File, Form, UploadFile, Request
from ..services.zip_handler import ZipHandlerService
from ..services.job_manager import JobManager
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import ZipError, TranscriboError
from ..types import (
    JobType,
    JobPriority,
    ZipValidationResult,
    ZipFileInfo,
    ProgressStage,
    UserID
)
from ..utils.metrics import (
    ZIP_REQUESTS,
    ZIP_ERRORS,
    track_zip_request,
    track_zip_error
)
from ..utils.api import create_api_router
from ..utils.route_utils import (
    api_route_handler,
    create_response,
    create_error_response
)
from ..utils.dependencies import (
    ZipHandlerDep,
    JobManagerDep,
    get_current_user
)
from ..models.api import ApiResponse

router = create_api_router("/zip", ["zip"])

@router.post("/process", response_model=ApiResponse[Dict])
@api_route_handler("process_zip")
async def process_zip(
    request: Request,
    file: UploadFile = File(...),
    metadata: Optional[Dict] = Form(None),
    encrypt: bool = Form(True),
    user_id: Optional[UserID] = Depends(get_current_user),
    service: ZipHandlerService = Depends(ZipHandlerDep),
    job_manager: JobManager = Depends(JobManagerDep)
) -> ApiResponse[Dict]:
    """Process a ZIP file.
    
    Args:
        file: ZIP file to process
        metadata: Optional metadata
        encrypt: Whether to encrypt extracted files
        service: ZIP handler service
        
    Returns:
        Processing result with job ID
        
    Raises:
        HTTPException: If processing fails
    """
    # Track request
    ZIP_REQUESTS.inc()
    track_zip_request()

    try:
        # Validate file
        if not service.is_zip_file(file.filename):
            return create_error_response(
                request,
                "File must be a ZIP archive",
                "INVALID_FILE_TYPE",
                400
            )
            
        # Save file to temporary location
        temp_file = os.path.join(
            os.getenv("TEMP_DIR", "/tmp"),
            f"upload_{os.path.basename(file.filename)}"
        )
        try:
            with open(temp_file, "wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            return create_error_response(
                request,
                f"Failed to save file: {str(e)}",
                "FILE_SAVE_ERROR",
                500
            )
            
        # Create job
        job = await job_manager.create_job(
            job_type=JobType.ZIP_PROCESSING,
            priority=JobPriority.NORMAL,
            owner_id=user_id,
            metadata={
                "filename": file.filename,
                "content_type": file.content_type,
                "size": os.path.getsize(temp_file),
                "user_metadata": metadata,
                "encrypt": encrypt,
                "stage": str(ProgressStage.UPLOADING),
                "progress": 0
            }
        )
        
        # Process ZIP file asynchronously
        async def process():
            try:
                # Update progress callback
                async def progress_callback(stage: str, progress: float):
                    await job_manager.update_job(
                        job.id,
                        metadata={
                            "stage": stage,
                            "progress": progress
                        }
                    )
                
                # Process ZIP file
                result = await service.process_zip_file(
                    file_path=temp_file,
                    job_id=job.id,
                    progress_callback=progress_callback,
                    encrypt=encrypt
                )
                
                # Create transcription jobs for processed files
                if result.is_combined:
                    # Create job for combined file
                    transcription_job = await job_manager.create_job(
                        job_type=JobType.TRANSCRIPTION,
                        priority=JobPriority.NORMAL,
                        owner_id=user_id,
                        metadata={
                            "parent_job_id": job.id,
                            "file_id": result.combined_file_id,
                            "is_combined": True,
                            "source_files": [f["file_id"] for f in result.original_files],
                            **(metadata or {})
                        }
                    )
                else:
                    # Create job for single file
                    transcription_job = await job_manager.create_job(
                        job_type=JobType.TRANSCRIPTION,
                        priority=JobPriority.NORMAL,
                        owner_id=user_id,
                        metadata={
                            "parent_job_id": job.id,
                            "file_id": result.combined_file_id,
                            "is_combined": False,
                            **(metadata or {})
                        }
                    )
                
                # Update parent job with child job ID
                await job_manager.update_job(
                    job.id,
                    metadata={
                        "child_jobs": [str(transcription_job.id)],
                        "stage": str(ProgressStage.COMPLETED),
                        "progress": 100
                    }
                )
                    
            except Exception as e:
                # Update job on error
                await job_manager.update_job(
                    job.id,
                    metadata={
                        "stage": str(ProgressStage.FAILED),
                        "progress": 0,
                        "error": str(e)
                    }
                )
                raise
            finally:
                # Clean up temporary file
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except Exception as e:
                    log_warning(f"Failed to remove temporary file: {str(e)}")
        
        # Start processing
        asyncio.create_task(process())
        
        return create_response(
            {
                "job_id": str(job.id),
                "status": "processing"
            },
            request
        )

    except ZipError as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"ZIP processing error: {str(e)}")
        return create_error_response(
            request,
            str(e),
            "ZIP_ERROR",
            400,
            details=getattr(e, "details", None)
        )
    except Exception as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"Error processing ZIP file: {str(e)}")
        return create_error_response(
            request,
            "Failed to process ZIP file",
            "INTERNAL_ERROR",
            500
        )

@router.post("/validate", response_model=ApiResponse[ZipValidationResult])
@api_route_handler("validate_zip")
async def validate_zip(
    request: Request,
    file: UploadFile = File(...),
    service: ZipHandlerService = Depends(ZipHandlerDep)
) -> ApiResponse[ZipValidationResult]:
    """Validate a ZIP file.
    
    Args:
        file: ZIP file to validate
        service: ZIP handler service
        
    Returns:
        Validation result
        
    Raises:
        HTTPException: If validation fails
    """
    # Track request
    ZIP_REQUESTS.inc()
    track_zip_request()

    try:
        # Validate file
        if not service.is_zip_file(file.filename):
            return create_response(
                ZipValidationResult(
                    is_valid=False,
                    file_count=0,
                    total_size=0,
                    audio_files=[],
                    errors=["File must be a ZIP archive"]
                ),
                request
            )
            
        # Save file to temporary location
        temp_file = os.path.join(
            os.getenv("TEMP_DIR", "/tmp"),
            f"validate_{os.path.basename(file.filename)}"
        )
        try:
            with open(temp_file, "wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            return create_error_response(
                request,
                f"Failed to save file: {str(e)}",
                "FILE_SAVE_ERROR",
                500
            )
            
        try:
            # Validate ZIP file
            result = await service.validate_zip_file(temp_file)
            return create_response(result, request)
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                log_warning(f"Failed to remove temporary file: {str(e)}")

    except ZipError as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"ZIP validation error: {str(e)}")
        return create_error_response(
            request,
            str(e),
            "ZIP_ERROR",
            400,
            details=getattr(e, "details", None)
        )
    except Exception as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"Error validating ZIP file: {str(e)}")
        return create_error_response(
            request,
            "Failed to validate ZIP file",
            "INTERNAL_ERROR",
            500
        )

@router.post("/info", response_model=ApiResponse[ZipFileInfo])
@api_route_handler("get_zip_info")
async def get_zip_info(
    request: Request,
    file: UploadFile = File(...),
    service: ZipHandlerService = Depends(ZipHandlerDep)
) -> ApiResponse[ZipFileInfo]:
    """Get ZIP file information.
    
    Args:
        file: ZIP file to get info for
        service: ZIP handler service
        
    Returns:
        ZIP file information
        
    Raises:
        HTTPException: If getting info fails
    """
    # Track request
    ZIP_REQUESTS.inc()
    track_zip_request()

    try:
        # Validate file
        if not service.is_zip_file(file.filename):
            return create_error_response(
                request,
                "File must be a ZIP archive",
                "INVALID_FILE_TYPE",
                400
            )
            
        # Save file to temporary location
        temp_file = os.path.join(
            os.getenv("TEMP_DIR", "/tmp"),
            f"info_{os.path.basename(file.filename)}"
        )
        try:
            with open(temp_file, "wb") as f:
                content = await file.read()
                f.write(content)
        except Exception as e:
            return create_error_response(
                request,
                f"Failed to save file: {str(e)}",
                "FILE_SAVE_ERROR",
                500
            )
            
        try:
            # Get ZIP info
            with zipfile.ZipFile(temp_file, 'r') as zip_ref:
                info = zip_ref.getinfo(zip_ref.filelist[0])
                result = ZipFileInfo(
                    filename=file.filename,
                    size=os.path.getsize(temp_file),
                    compressed_size=info.compress_size,
                    is_encrypted=info.flag_bits & 0x1,
                    created_at=datetime.fromtimestamp(info.date_time),
                    modified_at=datetime.fromtimestamp(info.date_time),
                    comment=zip_ref.comment.decode() if zip_ref.comment else None,
                    files=[{
                        "filename": info.filename,
                        "size": info.file_size,
                        "compressed_size": info.compress_size,
                        "is_encrypted": info.flag_bits & 0x1,
                        "modified_at": datetime.fromtimestamp(info.date_time)
                    } for info in zip_ref.filelist]
                )
                return create_response(result, request)
        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                log_warning(f"Failed to remove temporary file: {str(e)}")

    except ZipError as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"ZIP info error: {str(e)}")
        return create_error_response(
            request,
            str(e),
            "ZIP_ERROR",
            400,
            details=getattr(e, "details", None)
        )
    except Exception as e:
        ZIP_ERRORS.inc()
        track_zip_error()
        log_error(f"Error getting ZIP info: {str(e)}")
        return create_error_response(
            request,
            "Failed to get ZIP info",
            "INTERNAL_ERROR",
            500
        )
