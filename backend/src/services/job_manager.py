"""Job management service."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import base64
import json
from uuid import UUID

from ..models.job import Job, JobStatus, TranscriptionOptions
from ..models.job_repository import JobRepository
from ..services.base import BaseService
from ..utils.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    TranscriboError
)
from ..types import (
    JobID,
    UserID,
    FileMetadata,
    ErrorContext
)

class JobManager(BaseService):
    """Job management service."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize service.
        
        Args:
            config: Service configuration
        """
        super().__init__(config)
        self.job_repository = JobRepository()
        
    async def initialize(self) -> None:
        """Initialize service."""
        await super().initialize()
        await self.job_repository.initialize()
        
    async def create_job(
        self,
        user_id: Optional[UserID],
        file_data: Any,
        file_name: str,
        options: TranscriptionOptions,
        metadata: FileMetadata
    ) -> Dict[str, Any]:
        """Create transcription job.
        
        Args:
            user_id: Optional user ID
            file_data: File data
            file_name: Original file name
            options: Transcription options
            metadata: File metadata
            
        Returns:
            Created job
            
        Raises:
            ValidationError: If parameters invalid
            TranscriboError: If operation fails
        """
        try:
            # Create job
            job = Job(
                owner_id=user_id,
                file_name=file_name,
                status=JobStatus.PENDING,
                options=options,
                metadata=metadata,
                created_at=datetime.utcnow()
            )
            
            # Save to database
            await self.job_repository.create(job)
            
            return job.to_dict()
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_job",
                "user_id": user_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_name": file_name
                }
            }
            raise TranscriboError("Failed to create job", details=error_context)
            
    async def get_job_status(self, job_id: JobID) -> Dict[str, Any]:
        """Get job status.
        
        Args:
            job_id: Job ID to get
            
        Returns:
            Job status
            
        Raises:
            ResourceNotFoundError: If job not found
            TranscriboError: If operation fails
        """
        try:
            job = await self.job_repository.get(job_id)
            if not job:
                raise ResourceNotFoundError(f"Job {job_id} not found")
            return job.to_dict()
            
        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_job_status",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            raise TranscriboError("Failed to get job status", details=error_context)
            
    async def update_job_status(
        self,
        job_id: JobID,
        status: str,
        progress: Optional[float] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update job status.
        
        Args:
            job_id: Job ID to update
            status: New status
            progress: Optional progress percentage
            error: Optional error message
            
        Returns:
            Updated job
            
        Raises:
            ResourceNotFoundError: If job not found
            ValidationError: If status invalid
            TranscriboError: If operation fails
        """
        try:
            # Get job
            job = await self.job_repository.get(job_id)
            if not job:
                raise ResourceNotFoundError(f"Job {job_id} not found")
                
            # Update status
            job.status = JobStatus(status)
            if progress is not None:
                job.progress = progress
            if error:
                job.error = error
            job.updated_at = datetime.utcnow()
            
            # Save to database
            await self.job_repository.update(job)
            
            return job.to_dict()
            
        except (ResourceNotFoundError, ValidationError):
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "update_job_status",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "status": status
                }
            }
            raise TranscriboError("Failed to update job status", details=error_context)
            
    async def list_jobs_with_cursor(
        self,
        cursor: Optional[str] = None,
        limit: int = 100,
        sort_field: str = "created_at",
        sort_direction: str = "desc",
        filters: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str], int]:
        """List jobs with cursor-based pagination.
        
        Args:
            cursor: Optional cursor for pagination
            limit: Maximum number of jobs to return
            sort_field: Field to sort by
            sort_direction: Sort direction (asc/desc)
            filters: Optional filters to apply
            
        Returns:
            Tuple of (jobs list, next cursor, total count)
            
        Raises:
            ValidationError: If parameters invalid
            TranscriboError: If operation fails
        """
        try:
            # Decode cursor if provided
            cursor_data = None
            if cursor:
                try:
                    cursor_json = base64.b64decode(cursor.encode()).decode()
                    cursor_data = json.loads(cursor_json)
                except Exception as e:
                    raise ValidationError("Invalid cursor format")
                    
            # Get total count
            total = await self.job_repository.count(filters or {})
            
            # Get jobs
            jobs = await self.job_repository.find_with_cursor(
                cursor_data=cursor_data,
                limit=limit + 1,  # Get one extra to check if there are more
                sort_field=sort_field,
                sort_direction=sort_direction,
                filters=filters or {}
            )
            
            # Check if there are more results
            has_more = len(jobs) > limit
            if has_more:
                jobs = jobs[:limit]  # Remove extra item
                
                # Create next cursor
                last_job = jobs[-1]
                next_cursor_data = {
                    "last_id": str(last_job.id),
                    "last_value": str(getattr(last_job, sort_field))
                }
                next_cursor = base64.b64encode(
                    json.dumps(next_cursor_data).encode()
                ).decode()
            else:
                next_cursor = None
                
            return [job.to_dict() for job in jobs], next_cursor, total
            
        except ValidationError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "list_jobs",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "filters": filters
                }
            }
            raise TranscriboError("Failed to list jobs", details=error_context)
