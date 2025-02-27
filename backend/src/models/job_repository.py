"""Job repository."""

from typing import Dict, Any, List, Optional, cast
from datetime import datetime
from sqlalchemy import select, desc, asc, func, and_
from uuid import UUID

from .base import BaseRepository
from .job import Job
from ..utils.exceptions import ValidationError
from ..types import ErrorContext

class JobRepository(BaseRepository):
    """Job repository."""
    
    async def create(self, job: Job) -> None:
        """Create job.
        
        Args:
            job: Job to create
        """
        async with self.session.begin():
            self.session.add(job)
            
    async def get(self, job_id: UUID) -> Optional[Job]:
        """Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job if found, None otherwise
        """
        query = select(Job).where(Job.id == job_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()
        
    async def update(self, job: Job) -> None:
        """Update job.
        
        Args:
            job: Job to update
        """
        async with self.session.begin():
            await self.session.merge(job)
            
    async def delete(self, job_id: UUID) -> None:
        """Delete job.
        
        Args:
            job_id: Job ID to delete
        """
        async with self.session.begin():
            job = await self.get(job_id)
            if job:
                await self.session.delete(job)
                
    async def count(self, filters: Dict[str, Any]) -> int:
        """Count jobs matching filters.
        
        Args:
            filters: Filters to apply
            
        Returns:
            Number of matching jobs
        """
        query = select(func.count()).select_from(Job)
        
        # Apply filters
        if filters.get("user_id"):
            query = query.where(Job.owner_id == filters["user_id"])
        if filters.get("language"):
            query = query.where(Job.options["language"].astext == filters["language"])
            
        result = await self.session.execute(query)
        return cast(int, result.scalar())
        
    async def find_with_cursor(
        self,
        cursor_data: Optional[Dict[str, Any]],
        limit: int,
        sort_field: str,
        sort_direction: str,
        filters: Dict[str, Any]
    ) -> List[Job]:
        """Find jobs with cursor-based pagination.
        
        Args:
            cursor_data: Optional cursor data
            limit: Maximum number of jobs to return
            sort_field: Field to sort by
            sort_direction: Sort direction (asc/desc)
            filters: Filters to apply
            
        Returns:
            List of jobs
            
        Raises:
            ValidationError: If parameters invalid
        """
        try:
            # Build base query
            query = select(Job)
            
            # Apply filters
            if filters.get("user_id"):
                query = query.where(Job.owner_id == filters["user_id"])
            if filters.get("language"):
                query = query.where(Job.options["language"].astext == filters["language"])
                
            # Apply cursor conditions
            if cursor_data:
                last_id = UUID(cursor_data["last_id"])
                last_value = cursor_data["last_value"]
                
                # Get sort column
                sort_col = getattr(Job, sort_field)
                if not sort_col:
                    raise ValidationError(f"Invalid sort field: {sort_field}")
                    
                # Add cursor conditions
                if sort_direction.lower() == "desc":
                    query = query.where(
                        and_(
                            sort_col < last_value,
                            Job.id != last_id
                        )
                    )
                else:
                    query = query.where(
                        and_(
                            sort_col > last_value,
                            Job.id != last_id
                        )
                    )
                    
            # Apply sorting
            sort_col = getattr(Job, sort_field)
            if sort_direction.lower() == "desc":
                query = query.order_by(desc(sort_col), desc(Job.id))
            else:
                query = query.order_by(asc(sort_col), asc(Job.id))
                
            # Apply limit
            query = query.limit(limit)
            
            # Execute query
            result = await self.session.execute(query)
            return list(result.scalars().all())
            
        except ValidationError:
            raise
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "find_jobs",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "filters": filters,
                    "sort": {
                        "field": sort_field,
                        "direction": sort_direction
                    }
                }
            }
            raise ValidationError("Failed to find jobs", details=error_context)
