"""Job management routes."""

from fastapi import APIRouter, Depends, status
from typing import List, Optional, cast
from datetime import datetime
from ..models.job import JobResponse, JobUpdate, TranscriptionOptions
from ..services.job_manager import JobManager
from ..utils.exceptions import (
    ResourceNotFoundError,
    AuthorizationError,
    TranscriboError,
    ValidationError
)
from ..types import (
    ErrorContext,
    JobID,
    UserID
)
from ..utils.route_utils import (
    route_handler,
    map_to_response
)
from ..utils.dependencies import JobManagerDep

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
@route_handler("get_job", JobResponse)
async def get_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> JobResponse:
    """Get job information.
    
    Args:
        job_id: Job ID to get
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        
    Returns:
        Job response
        
    Raises:
        ResourceNotFoundError: If job not found
        AuthorizationError: If user not authorized
        TranscriboError: If operation fails
    """
    try:
        job = await job_manager.get_job_status(job_id)
        
        # Check authorization
        if user_id and job.get('owner_id') != user_id:
            error_context: ErrorContext = {
                "operation": "get_job",
                "resource_id": job_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": "Not authorized"}
            }
            raise AuthorizationError("Not authorized to access this job", details=error_context)
            
        return map_to_response(job, JobResponse)
        
    except ResourceNotFoundError:
        raise
    except AuthorizationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "get_job",
            "resource_id": job_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to get job", details=error_context)

@router.get(
    "/",
    response_model=List[JobResponse],
    summary="List Jobs",
    description="List jobs for the authenticated user"
)
@route_handler("list_jobs", List[JobResponse])
async def list_jobs(
    user_id: Optional[UserID] = None,  # Set by auth middleware
    limit: Optional[int] = 100,
    offset: Optional[int] = 0,
    language: Optional[str] = None,
    job_manager: JobManager = Depends(JobManagerDep)
) -> List[JobResponse]:
    """List jobs for a user.
    
    Args:
        user_id: Optional user ID for filtering
        limit: Maximum number of jobs to return
        offset: Number of jobs to skip
        language: Optional language filter
        job_manager: Job manager service
        
    Returns:
        List of job responses
        
    Raises:
        ValidationError: If parameters invalid
        TranscriboError: If operation fails
    """
    try:
        # Validate parameters
        if limit < 0 or offset < 0:
            error_context: ErrorContext = {
                "operation": "list_jobs",
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
        return [map_to_response(job, JobResponse) for job in jobs]
        
    except ValidationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "list_jobs",
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "filters": filters
            }
        }
        raise TranscriboError("Failed to list jobs", details=error_context)

@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    summary="Cancel Job",
    description="Cancel a running job"
)
@route_handler("cancel_job", JobResponse)
async def cancel_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> JobResponse:
    """Cancel a job.
    
    Args:
        job_id: Job ID to cancel
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        
    Returns:
        Updated job response
        
    Raises:
        ResourceNotFoundError: If job not found
        AuthorizationError: If user not authorized
        TranscriboError: If operation fails
    """
    try:
        # Check authorization
        job = await job_manager.get_job_status(job_id)
        if user_id and job.get('owner_id') != user_id:
            error_context: ErrorContext = {
                "operation": "cancel_job",
                "resource_id": job_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": "Not authorized"}
            }
            raise AuthorizationError("Not authorized to cancel this job", details=error_context)
            
        # Cancel job
        await job_manager.update_job_status(job_id, "cancelled")
        updated_job = await job_manager.get_job_status(job_id)
        return map_to_response(updated_job, JobResponse)
        
    except ResourceNotFoundError:
        raise
    except AuthorizationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "cancel_job",
            "resource_id": job_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to cancel job", details=error_context)

@router.post(
    "/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry Job",
    description="Retry a failed job"
)
@route_handler("retry_job", JobResponse)
async def retry_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> JobResponse:
    """Retry a failed job.
    
    Args:
        job_id: Job ID to retry
        user_id: Optional user ID for authorization
        job_manager: Job manager service
        
    Returns:
        Updated job response
        
    Raises:
        ResourceNotFoundError: If job not found
        AuthorizationError: If user not authorized
        ValidationError: If job cannot be retried
        TranscriboError: If operation fails
    """
    try:
        # Check authorization
        job = await job_manager.get_job_status(job_id)
        if user_id and job.get('owner_id') != user_id:
            error_context: ErrorContext = {
                "operation": "retry_job",
                "resource_id": job_id,
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": "Not authorized"}
            }
            raise AuthorizationError("Not authorized to retry this job", details=error_context)
            
        # Validate job can be retried
        if job.get('status') not in ['error', 'cancelled']:
            error_context: ErrorContext = {
                "operation": "retry_job",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": "Invalid job status",
                    "status": job.get('status')
                }
            }
            raise ValidationError("Job cannot be retried", details=error_context)
            
        # Retry job
        await job_manager.update_job_status(job_id, "pending")
        updated_job = await job_manager.get_job_status(job_id)
        return map_to_response(updated_job, JobResponse)
        
    except ResourceNotFoundError:
        raise
    except AuthorizationError:
        raise
    except ValidationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "retry_job",
            "resource_id": job_id,
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to retry job", details=error_context)
