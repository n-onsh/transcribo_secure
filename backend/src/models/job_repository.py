"""Job repository for database operations."""

from datetime import datetime
from typing import Dict, Optional, List
from ..utils.logging import log_info, log_error
from ..utils.exceptions import TranscriboError
from ..services.repository import BaseRepository
from .job import Job, JobStatus, JobPriority

class JobRepository(BaseRepository):
    """Repository for job database operations."""

    async def create_job(self, job_data: Dict) -> str:
        """Create a job record in the database.
        
        Args:
            job_data: Job data including options
            
        Returns:
            Created job ID
            
        Raises:
            TranscriboError: If creation fails
        """
        try:
            # Start transaction
            queries = []
            
            # Insert job record
            job_query = """
            INSERT INTO jobs (
                id, owner_id, file_name, file_size, status, priority,
                is_zip, parent_job_id, metadata
            ) VALUES (
                $id, $owner_id, $file_name, $file_size, $status, $priority,
                $is_zip, $parent_job_id, $metadata
            )
            """
            
            queries.append({
                'query': job_query,
                'params': {
                    'id': job_data['job_id'],
                    'owner_id': job_data['owner_id'],
                    'file_name': job_data['file_name'],
                    'file_size': job_data['file_size'],
                    'status': job_data.get('status', JobStatus.PENDING),
                    'priority': job_data.get('priority', JobPriority.NORMAL),
                    'is_zip': job_data.get('is_zip', False),
                    'parent_job_id': job_data.get('parent_job_id'),
                    'metadata': job_data.get('metadata', {})
                }
            })
            
            # Insert job options
            if 'options' in job_data:
                options_query = """
                INSERT INTO job_options (
                    job_id, vocabulary, generate_srt, language
                ) VALUES (
                    $job_id, $vocabulary, $generate_srt, $language
                )
                """
                
                options = job_data['options']
                queries.append({
                    'query': options_query,
                    'params': {
                        'job_id': job_data['job_id'],
                        'vocabulary': options.get('vocabulary', []),
                        'generate_srt': options.get('generate_srt', True),
                        'language': options.get('language', 'de')
                    }
                })
            
            # Execute transaction
            await self.session.execute_transaction(queries)
            
            return job_data['job_id']
            
        except Exception as e:
            log_error(f"Failed to create job record: {str(e)}")
            raise TranscriboError(
                "Failed to create job record",
                details={"error": str(e)}
            )

    async def update_status(self, job_id: str, status: str, metadata: Optional[Dict] = None):
        """Update job status.
        
        Args:
            job_id: Job ID
            status: New status
            metadata: Optional metadata to update
            
        Raises:
            TranscriboError: If update fails
        """
        try:
            query = """
            UPDATE jobs
            SET status = $status,
                updated_at = CURRENT_TIMESTAMP,
                metadata = COALESCE(metadata, '{}'::jsonb) || $metadata::jsonb
            WHERE id = $id
            """
            
            await self.session.execute_query(
                query,
                {
                    'id': job_id,
                    'status': status,
                    'metadata': metadata or {}
                }
            )
            
        except Exception as e:
            log_error(f"Failed to update job status: {str(e)}")
            raise TranscriboError(
                "Failed to update job status",
                details={"job_id": job_id, "error": str(e)}
            )

    async def update_error(self, job_id: str, error: str) -> Tuple[int, int]:
        """Update job error and retry information.
        
        Args:
            job_id: Job ID
            error: Error message
            
        Returns:
            Tuple of (retry_count, max_retries)
            
        Raises:
            TranscriboError: If update fails
        """
        try:
            query = """
            UPDATE jobs
            SET error = $error,
                status = $status,
                retry_count = retry_count + 1,
                next_retry_at = CASE
                    WHEN retry_count < max_retries THEN
                        CURRENT_TIMESTAMP + (INTERVAL '1 minute' * POWER(2, retry_count))
                    ELSE NULL
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $id
            RETURNING retry_count, max_retries
            """
            
            result = await self.session.execute_query(
                query,
                {
                    'id': job_id,
                    'error': error,
                    'status': JobStatus.FAILED
                }
            )
            
            if result and len(result) > 0:
                return (result[0]['retry_count'], result[0]['max_retries'])
            return (0, 0)
            
        except Exception as e:
            log_error(f"Failed to update job error: {str(e)}")
            raise TranscriboError(
                "Failed to update job error",
                details={"job_id": job_id, "error": str(e)}
            )

    async def get_details(self, job_id: str) -> Optional[Dict]:
        """Get job details.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job details if found, None otherwise
            
        Raises:
            TranscriboError: If query fails
        """
        try:
            query = """
            SELECT j.*, jo.vocabulary, jo.generate_srt, jo.language
            FROM jobs j
            LEFT JOIN job_options jo ON j.id = jo.job_id
            WHERE j.id = $id
            """
            
            results = await self.session.execute_query(query, {'id': job_id})
            
            if results and len(results) > 0:
                job = results[0]
                return {
                    'id': job['id'],
                    'owner_id': job['owner_id'],
                    'file_name': job['file_name'],
                    'file_size': job['file_size'],
                    'status': job['status'],
                    'progress': job['progress'],
                    'error': job['error'],
                    'is_zip': job['is_zip'],
                    'zip_progress': job['zip_progress'],
                    'sub_jobs': job['sub_jobs'],
                    'parent_job_id': job['parent_job_id'],
                    'options': {
                        'vocabulary': job['vocabulary'] or [],
                        'generate_srt': job['generate_srt'],
                        'language': job['language']
                    } if job['language'] is not None else None,
                    'created_at': job['created_at'],
                    'updated_at': job['updated_at']
                }
            
            return None
            
        except Exception as e:
            log_error(f"Failed to get job details: {str(e)}")
            raise TranscriboError(
                "Failed to get job details",
                details={"job_id": job_id, "error": str(e)}
            )

    async def list_filtered(self, filters: Optional[Dict] = None) -> List[Dict]:
        """Get filtered jobs.
        
        Args:
            filters: Optional filter parameters
            
        Returns:
            List of job details
            
        Raises:
            TranscriboError: If query fails
        """
        try:
            query = """
            SELECT j.*, jo.vocabulary, jo.generate_srt, jo.language
            FROM jobs j
            LEFT JOIN job_options jo ON j.id = jo.job_id
            WHERE 1=1
            """
            
            params = {}
            
            if filters:
                if 'owner_id' in filters:
                    query += " AND j.owner_id = $owner_id"
                    params['owner_id'] = filters['owner_id']
                    
                if 'status' in filters:
                    query += " AND j.status = $status"
                    params['status'] = filters['status']
                    
                if 'is_zip' in filters:
                    query += " AND j.is_zip = $is_zip"
                    params['is_zip'] = filters['is_zip']
                    
                if 'parent_job_id' in filters:
                    query += " AND j.parent_job_id = $parent_job_id"
                    params['parent_job_id'] = filters['parent_job_id']
            
            query += " ORDER BY j.priority DESC, j.created_at ASC"
            
            results = await self.session.execute_query(query, params)
            
            return [{
                'id': job['id'],
                'owner_id': job['owner_id'],
                'file_name': job['file_name'],
                'file_size': job['file_size'],
                'status': job['status'],
                'progress': job['progress'],
                'error': job['error'],
                'is_zip': job['is_zip'],
                'zip_progress': job['zip_progress'],
                'sub_jobs': job['sub_jobs'],
                'parent_job_id': job['parent_job_id'],
                'options': {
                    'vocabulary': job['vocabulary'] or [],
                    'generate_srt': job['generate_srt'],
                    'language': job['language']
                } if job['language'] is not None else None,
                'created_at': job['created_at'],
                'updated_at': job['updated_at']
            } for job in results]
            
        except Exception as e:
            log_error(f"Failed to get filtered jobs: {str(e)}")
            raise TranscriboError(
                "Failed to get filtered jobs",
                details={"error": str(e)}
            )
