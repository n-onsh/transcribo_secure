"""Job manager service."""

import uuid
from datetime import datetime
from typing import Dict, Optional, List, Any, cast
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import TranscriboError, ResourceNotFoundError
from .base import BaseService
from .database import DatabaseService
from ..models.job import JobModel, JobStatus, JobPriority, JobOptions
from ..models.job_repository import JobRepository
from ..types import (
    JobID,
    ServiceConfig,
    Result,
    ErrorContext,
    JSON,
    JSONValue,
    DBSession
)
from ..utils.metrics import (
    JOB_PROCESSING_TIME,
    JOB_STATUS_COUNT,
    JOB_ERROR_COUNT,
    ZIP_PROCESSING_TIME,
    ZIP_FILE_COUNT,
    track_job_processing,
    track_job_status,
    track_job_error,
    track_zip_processing
)

class ZipJobInfo(TypedDict):
    """Type definition for ZIP job tracking information."""
    status: str
    sub_jobs: List[JobID]
    progress: Dict[str, Any]
    error: Optional[str]

class JobManager(BaseService):
    """Service for managing job lifecycle."""

    def __init__(
        self,
        settings: ServiceConfig,
        database_service: Optional[DatabaseService] = None
    ) -> None:
        """Initialize job manager.
        
        Args:
            settings: Service settings
            database_service: Optional database service instance
        """
        super().__init__(settings)
        self.db: Optional[DatabaseService] = database_service
        self.repository: Optional[JobRepository] = None
        self.zip_jobs: Dict[JobID, ZipJobInfo] = {}  # Track ZIP jobs and their sub-jobs
        self.max_concurrent_jobs: int = 10
        self.job_timeout: int = 3600
        self.cleanup_interval: int = 3600

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize database if not provided
            if not self.db:
                self.db = DatabaseService(self.settings)
                await self.db.initialize()
                
            # Initialize job manager settings
            self.max_concurrent_jobs = int(self.settings.get('max_concurrent_jobs', 10))
            self.job_timeout = int(self.settings.get('job_timeout', 3600))
            self.cleanup_interval = int(self.settings.get('cleanup_interval', 3600))

            # Initialize repository
            if self.db:
                self.repository = JobRepository(self.db.pool, JobModel)

            # Create tables
            await self._create_tables()

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_job_manager",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize job manager: {str(e)}")
            raise TranscriboError(
                "Failed to initialize job manager",
                details=error_context
            )

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
        try:
            if self.db:
                await self.db.cleanup()
            self.zip_jobs.clear()

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_job_manager",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during job manager cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up job manager",
                details=error_context
            )

    async def create_job(self, job_data: Dict[str, Any]) -> JobID:
        """Create a new job.
        
        Args:
            job_data: Job data including options
            
        Returns:
            Created job ID
            
        Raises:
            TranscriboError: If creation fails
        """
        try:
            is_zip = job_data.get('file_type') == 'zip'
            
            # Create main job record
            job_id = JobID(str(uuid.uuid4()))
            job_data['job_id'] = job_id
            
            if is_zip:
                # Initialize ZIP job tracking
                self.zip_jobs[job_id] = {
                    'status': 'created',
                    'sub_jobs': [],
                    'progress': {
                        'stage': 'created',
                        'percent': 0
                    },
                    'error': None
                }
                job_data['is_zip'] = True
            
            # Create job record
            if self.repository:
                await self.repository.create_job(job_data)
            
            # Track job creation
            JOB_STATUS_COUNT.labels(status='created').inc()
            track_job_status('created')
            
            log_info(f"Created {'ZIP ' if is_zip else ''}job {job_id}")
            return job_id

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_job",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "job_data": job_data
                }
            }
            log_error(f"Error creating job: {str(e)}")
            raise TranscriboError(
                "Failed to create job",
                details=error_context
            )

    async def create_zip_sub_jobs(
        self,
        parent_job_id: JobID,
        file_list: List[str]
    ) -> List[JobID]:
        """Create sub-jobs for files in a ZIP archive.
        
        Args:
            parent_job_id: Parent ZIP job ID
            file_list: List of file paths
            
        Returns:
            List of created sub-job IDs
            
        Raises:
            TranscriboError: If creation fails
        """
        try:
            sub_job_ids: List[JobID] = []
            for file_path in file_list:
                sub_job_id = JobID(str(uuid.uuid4()))
                sub_job_data = {
                    'job_id': sub_job_id,
                    'parent_job_id': parent_job_id,
                    'file_path': file_path,
                    'is_sub_job': True
                }
                if self.repository:
                    await self.repository.create_job(sub_job_data)
                sub_job_ids.append(sub_job_id)
                
                if parent_job_id in self.zip_jobs:
                    self.zip_jobs[parent_job_id]['sub_jobs'].append(sub_job_id)
            
            ZIP_FILE_COUNT.inc(len(sub_job_ids))
            log_info(f"Created {len(sub_job_ids)} sub-jobs for ZIP job {parent_job_id}")
            return sub_job_ids
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_zip_sub_jobs",
                "resource_id": parent_job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_count": len(file_list)
                }
            }
            log_error(f"Error creating ZIP sub-jobs for {parent_job_id}: {str(e)}")
            raise TranscriboError(
                "Failed to create ZIP sub-jobs",
                details=error_context
            )

    async def update_job_status(
        self,
        job_id: JobID,
        status: str,
        metadata: Optional[Dict[str, JSONValue]] = None
    ) -> None:
        """Update job status.
        
        Args:
            job_id: Job ID
            status: New status
            metadata: Optional metadata
            
        Raises:
            ResourceNotFoundError: If job not found
            TranscriboError: If update fails
        """
        try:
            if not self.repository:
                raise TranscriboError("Repository not initialized")
                
            job_details = await self.repository.get_details(job_id)
            if not job_details:
                raise ResourceNotFoundError("job", job_id)
                
            is_zip = job_details.get('is_zip', False)
            is_sub_job = job_details.get('is_sub_job', False)
            
            # Update job status
            await self.repository.update_status(job_id, status, metadata)
            
            if is_zip:
                # Update ZIP job progress
                await self._update_zip_job_progress(job_id, status, metadata)
            elif is_sub_job and 'parent_job_id' in job_details:
                # Update parent ZIP job progress when sub-job status changes
                await self._update_zip_job_from_sub_job(
                    cast(JobID, job_details['parent_job_id']),
                    job_id,
                    status
                )
            
            # Track status change
            JOB_STATUS_COUNT.labels(status=status).inc()
            track_job_status(status)
            
            log_info(f"Updated {'ZIP ' if is_zip else ''}job {job_id} status to {status}")

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "update_job_status",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "status": status,
                    "metadata": metadata
                }
            }
            log_error(f"Error updating job {job_id} status: {str(e)}")
            raise TranscriboError(
                "Failed to update job status",
                details=error_context
            )

    async def handle_job_error(self, job_id: JobID, error: str) -> None:
        """Handle job error.
        
        Args:
            job_id: Job ID
            error: Error message
            
        Raises:
            ResourceNotFoundError: If job not found
            TranscriboError: If error handling fails
        """
        try:
            if not self.repository:
                raise TranscriboError("Repository not initialized")
                
            job_details = await self.repository.get_details(job_id)
            if not job_details:
                raise ResourceNotFoundError("job", job_id)
                
            is_zip = job_details.get('is_zip', False)
            is_sub_job = job_details.get('is_sub_job', False)
            
            # Track error
            JOB_ERROR_COUNT.inc()
            track_job_error()
            
            # Update job with error
            retry_count, max_retries = await self.repository.update_error(job_id, error)
            
            if is_zip:
                # Update ZIP job status
                self.zip_jobs[job_id]['status'] = 'error'
                self.zip_jobs[job_id]['error'] = error
            elif is_sub_job and 'parent_job_id' in job_details:
                # Update parent ZIP job when sub-job fails
                await self._handle_zip_sub_job_error(
                    cast(JobID, job_details['parent_job_id']),
                    job_id,
                    error
                )
            
            # If retries remain, update status back to pending
            if retry_count < max_retries:
                await self.repository.update_status(job_id, JobStatus.PENDING)
            
            log_error(f"{'ZIP ' if is_zip else ''}Job {job_id} failed with error: {error}")

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "handle_job_error",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "job_error": error
                }
            }
            log_error(f"Error handling job {job_id} error: {str(e)}")
            raise TranscriboError(
                "Failed to handle job error",
                details=error_context
            )

    async def get_job_status(self, job_id: JobID) -> Dict[str, Any]:
        """Get job status.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job status details
            
        Raises:
            ResourceNotFoundError: If job not found
            TranscriboError: If status retrieval fails
        """
        try:
            if not self.repository:
                raise TranscriboError("Repository not initialized")
                
            # Get job details
            job = await self.repository.get_details(job_id)
            if not job:
                raise ResourceNotFoundError("job", job_id)
            
            # Add ZIP-specific information
            if job.get('is_zip', False) and job_id in self.zip_jobs:
                zip_info = self.zip_jobs[job_id]
                job.update({
                    'zip_progress': zip_info['progress'],
                    'sub_jobs': zip_info['sub_jobs']
                })
            
            log_info(f"Retrieved status for {'ZIP ' if job.get('is_zip') else ''}job {job_id}")
            return job

        except ResourceNotFoundError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_job_status",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error getting job {job_id} status: {str(e)}")
            raise TranscriboError(
                "Failed to get job status",
                details=error_context
            )

    async def list_jobs(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """List jobs with optional filters.
        
        Args:
            filters: Optional filter parameters
            
        Returns:
            List of job details
            
        Raises:
            TranscriboError: If listing fails
        """
        try:
            if not self.repository:
                raise TranscriboError("Repository not initialized")
                
            # Get filtered jobs
            jobs = await self.repository.list_filtered(filters)
            log_info(f"Listed {len(jobs)} jobs")
            return jobs

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "list_jobs",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "filters": filters
                }
            }
            log_error(f"Error listing jobs: {str(e)}")
            raise TranscriboError(
                "Failed to list jobs",
                details=error_context
            )

    async def _create_tables(self) -> None:
        """Create required database tables."""
        try:
            if not self.db:
                raise TranscriboError("Database service not initialized")
                
            create_table_query = """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                duration FLOAT,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 1,
                progress FLOAT NOT NULL DEFAULT 0,
                error TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                max_retries INTEGER NOT NULL DEFAULT 3,
                next_retry_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                cancelled_at TIMESTAMP WITH TIME ZONE,
                estimated_time FLOAT,
                estimate_confidence FLOAT,
                metadata JSONB,
                is_zip BOOLEAN NOT NULL DEFAULT FALSE,
                zip_progress JSONB,
                sub_jobs TEXT[],
                parent_job_id TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS job_options (
                job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
                vocabulary TEXT[],
                generate_srt BOOLEAN NOT NULL DEFAULT TRUE,
                language TEXT NOT NULL DEFAULT 'de',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            await self.db.execute_query(create_table_query)
            log_info("Created job tables if not exist")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_tables",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to create job tables: {str(e)}")
            raise TranscriboError(
                "Failed to create job tables",
                details=error_context
            )

    async def _update_zip_job_progress(
        self,
        job_id: JobID,
        status: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update ZIP job progress based on status and metadata."""
        if job_id not in self.zip_jobs:
            return
        
        zip_job = self.zip_jobs[job_id]
        
        if status == 'extracting':
            zip_job['progress'] = {
                'stage': 'extracting',
                'percent': metadata.get('progress', 0) if metadata else 0
            }
        elif status == 'processing':
            zip_job['progress'] = {
                'stage': 'processing',
                'percent': metadata.get('progress', 0) if metadata else 0
            }
        elif status == 'completed':
            zip_job['progress'] = {
                'stage': 'completed',
                'percent': 100
            }
            # Track processing time
            if metadata and 'processing_time' in metadata:
                track_zip_processing(float(metadata['processing_time']))
        
        zip_job['status'] = status

    async def _update_zip_job_from_sub_job(
        self,
        parent_job_id: JobID,
        sub_job_id: JobID,
        status: str
    ) -> None:
        """Update ZIP job progress when a sub-job status changes."""
        if parent_job_id not in self.zip_jobs or not self.repository:
            return
        
        zip_job = self.zip_jobs[parent_job_id]
        total_jobs = len(zip_job['sub_jobs'])
        completed_jobs = sum(1 for job_id in zip_job['sub_jobs'] 
                           if (await self.repository.get_details(job_id))['status'] == 'completed')
        
        progress = (completed_jobs / total_jobs) * 100 if total_jobs > 0 else 0
        
        zip_job['progress'] = {
            'stage': 'processing',
            'percent': progress
        }
        
        if completed_jobs == total_jobs:
            zip_job['status'] = 'completed'
            zip_job['progress']['stage'] = 'completed'
            zip_job['progress']['percent'] = 100

    async def _handle_zip_sub_job_error(
        self,
        parent_job_id: JobID,
        sub_job_id: JobID,
        error: str
    ) -> None:
        """Handle error in ZIP sub-job."""
        if parent_job_id not in self.zip_jobs or not self.repository:
            return
        
        zip_job = self.zip_jobs[parent_job_id]
        zip_job['status'] = 'error'
        zip_job['error'] = f"Sub-job {sub_job_id} failed: {error}"
        
        # Cancel other pending sub-jobs
        for job_id in zip_job['sub_jobs']:
            if job_id != sub_job_id:
                job_details = await self.repository.get_details(job_id)
                if job_details['status'] not in ['completed', 'error']:
                    await self.repository.update_status(job_id, JobStatus.CANCELLED)
