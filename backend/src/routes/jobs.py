"""Job management routes."""

from fastapi import Depends, status
from typing import Optional, cast
from datetime import datetime

from ..models.job import JobResponse, JobUpdate, TranscriptionOptions
from ..models.api import ApiResponse, ApiListResponse
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
from ..utils.api import create_api_router
from ..utils.route_utils import (
    api_route_handler,
    validate_pagination_params,
    create_response,
    create_list_response
)
from ..utils.dependencies import JobManagerDep

router = create_api_router("/jobs", ["jobs"])

@router.get(
    "/{job_id}",
    response_model=ApiResponse[JobResponse],
    summary="Get Job",
    description="Get job status and information"
)
@api_route_handler("get_job", JobResponse)
async def get_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> ApiResponse[JobResponse]:
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
            
        return create_response(job, JobResponse)
        
    except (ResourceNotFoundError, AuthorizationError):
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
    response_model=ApiListResponse[JobResponse],
    summary="List Jobs",
    description="List jobs for the authenticated user"
)
@api_route_handler("list_jobs", JobResponse)
async def list_jobs(
    user_id: Optional[UserID] = None,  # Set by auth middleware
    cursor: Optional[str] = None,
    limit: Optional[int] = None,
    sort_field: Optional[str] = None,
    sort_direction: Optional[str] = None,
    language: Optional[str] = None,
    job_manager: JobManager = Depends(JobManagerDep)
) -> ApiListResponse[JobResponse]:
    """List jobs for a user.
    
    Args:
        user_id: Optional user ID for filtering
        cursor: Pagination cursor
        limit: Maximum number of jobs to return
        sort_field: Field to sort by
        sort_direction: Sort direction (asc/desc)
        language: Optional language filter
        job_manager: Job manager service
        
    Returns:
        List of job responses
        
    Raises:
        ValidationError: If parameters invalid
        TranscriboError: If operation fails
    """
    try:
        # Validate pagination parameters
        pagination = validate_pagination_params(
            limit=limit,
            cursor=cursor,
            sort_field=sort_field,
            sort_direction=sort_direction
        )
        
        # Get jobs with cursor
        jobs, next_cursor, total = await job_manager.list_jobs_with_cursor(
            cursor=pagination.cursor,
            limit=pagination.limit,
            sort_field=pagination.sort_field,
            sort_direction=pagination.sort_direction,
            filters={
                "user_id": user_id,
                "language": language
            }
        )
        
        return create_list_response(
            jobs,
            JobResponse,
            total=total,
            limit=pagination.limit,
            next_cursor=next_cursor
        )
        
    except ValidationError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "list_jobs",
            "user_id": user_id,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "filters": {
                    "user_id": user_id,
                    "language": language
                }
            }
        }
        raise TranscriboError("Failed to list jobs", details=error_context)

@router.post(
    "/{job_id}/cancel",
    response_model=ApiResponse[JobResponse],
    summary="Cancel Job",
    description="Cancel a running job"
)
@api_route_handler("cancel_job", JobResponse)
async def cancel_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> ApiResponse[JobResponse]:
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
        return create_response(updated_job, JobResponse)
        
    except (ResourceNotFoundError, AuthorizationError):
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
    response_model=ApiResponse[JobResponse],
    summary="Retry Job",
    description="Retry a failed job"
)
@api_route_handler("retry_job", JobResponse)
async def retry_job(
    job_id: JobID,
    user_id: Optional[UserID] = None,  # Set by auth middleware
    job_manager: JobManager = Depends(JobManagerDep)
) -> ApiResponse[JobResponse]:
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
        return create_response(updated_job, JobResponse)
        
    except (ResourceNotFoundError, AuthorizationError, ValidationError):
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
