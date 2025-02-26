from fastapi import APIRouter, Depends, status
from typing import List, Optional
from ..models.job import JobResponse, JobUpdate, TranscriptionOptions
from ..services.job_manager import JobManager
from ..utils.exceptions import (
    ResourceNotFoundError,
    AuthorizationError,
    TranscriboError
)
from ..utils.metrics import track_time, DB_OPERATION_DURATION
from ..utils.dependencies import JobManager as JobManagerDep

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"]
)

def _map_job_to_response(job) -> JobResponse:
    """Map job model to response model."""
    return JobResponse(
        id=job.id,
        file_name=job.file_name,
        status=job.status,
        progress=job.progress,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
        options=job.options,
        language=job.options.language if job.options else None,
        supported_languages=job.options.supported_languages if job.options else None,
        is_zip=job.is_zip,
        zip_progress=job.zip_progress,
        sub_jobs=job.sub_jobs,
        parent_job_id=job.parent_job_id
    )

@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get Job",
    description="Get job status and information"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_job"})
async def get_job(
    job_id: str,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
):
    """Get job information"""
    job = await job_manager.get_job(job_id, user_id)
    return _map_job_to_response(job)

@router.get(
    "/",
    response_model=List[JobResponse],
    summary="List Jobs",
    description="List jobs for the authenticated user"
)
@track_time(DB_OPERATION_DURATION, {"operation": "list_jobs"})
async def list_jobs(
    user_id: str = None,  # Set by auth middleware
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    language: Optional[str] = None,
    job_manager: JobManager = Depends(JobManagerDep)
):
    """List jobs for a user"""
    jobs = await job_manager.list_jobs(
        user_id=user_id,
        limit=limit,
        offset=offset,
        language=language
    )
    return [_map_job_to_response(job) for job in jobs]

@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel Job",
    description="Cancel a running job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "cancel_job"})
async def cancel_job(
    job_id: str,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
):
    """Cancel a job"""
    job = await job_manager.cancel_job(job_id, user_id)
    return _map_job_to_response(job)

@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry Job",
    description="Retry a failed job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "retry_job"})
async def retry_job(
    job_id: str,
    user_id: str = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
):
    """Retry a failed job"""
    job = await job_manager.retry_job(job_id, user_id)
    return _map_job_to_response(job)
