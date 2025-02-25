from fastapi import APIRouter, HTTPException, status
from typing import List, Optional
from ..models.job import JobResponse, JobUpdate, TranscriptionOptions
from ..services.interfaces import JobManagerInterface
from ..services.provider import service_provider
from ..utils.exceptions import ResourceNotFoundError, AuthorizationError
from ..utils.metrics import track_time, DB_OPERATION_DURATION

router = APIRouter(
    prefix="/jobs",
    tags=["jobs"]
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
    user_id: str = None  # Set by auth middleware
):
    """Get job information"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get job
        job = await job_manager.get_job(job_id, user_id)
        if not job:
            raise ResourceNotFoundError("job", job_id)

        return JobResponse(
            id=job.id,
            file_name=job.file_name,
            status=job.status,
            progress=job.progress,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
            options=job.options,
            language=job.options.language,
            supported_languages=job.options.supported_languages
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
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
    response_model=List[JobResponse],
    summary="List Jobs",
    description="List jobs for the authenticated user"
)
@track_time(DB_OPERATION_DURATION, {"operation": "list_jobs"})
async def list_jobs(
    user_id: str = None,  # Set by auth middleware
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    language: Optional[str] = None
):
    """List jobs for a user"""
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
            JobResponse(
                id=job.id,
                file_name=job.file_name,
                status=job.status,
                progress=job.progress,
                error=job.error,
                created_at=job.created_at,
                completed_at=job.completed_at,
                options=job.options,
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

@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel Job",
    description="Cancel a running job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "cancel_job"})
async def cancel_job(
    job_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Cancel a job"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Cancel job
        job = await job_manager.cancel_job(job_id, user_id)

        return JobResponse(
            id=job.id,
            file_name=job.file_name,
            status=job.status,
            progress=job.progress,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
            options=job.options,
            language=job.options.language,
            supported_languages=job.options.supported_languages
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
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

@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry Job",
    description="Retry a failed job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "retry_job"})
async def retry_job(
    job_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Retry a failed job"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Retry job
        job = await job_manager.retry_job(job_id, user_id)

        return JobResponse(
            id=job.id,
            file_name=job.file_name,
            status=job.status,
            progress=job.progress,
            error=job.error,
            created_at=job.created_at,
            completed_at=job.completed_at,
            options=job.options,
            language=job.options.language,
            supported_languages=job.options.supported_languages
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
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
