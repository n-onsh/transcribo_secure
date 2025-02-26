"""Base repository class for database operations."""

from datetime import datetime
from typing import Dict, List, Optional, Type, TypeVar, Any, Generic, cast
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.sql import Select
from sqlalchemy.sql.expression import BinaryExpression
from ..utils.logging import log_info, log_error
from ..utils.exceptions import ResourceNotFoundError, TranscriboError
from ..utils.metrics import track_time, DB_OPERATION_DURATION
from ..models.base import Base
from ..types import (
    RepositoryProtocol,
    DBSession,
    QueryResult,
    TransactionResult,
    Result,
    ErrorContext,
    Pagination
)

T = TypeVar('T', bound=Base)

class BaseRepository(Generic[T], RepositoryProtocol[T]):
    """Base repository for database operations."""
    
    def __init__(self, session: DBSession, model_class: Type[T]) -> None:
        """Initialize repository.
        
        Args:
            session: SQLAlchemy async session
            model_class: SQLAlchemy model class
        """
        self.session: DBSession = session
        self.model_class: Type[T] = model_class
        
    @track_time(DB_OPERATION_DURATION)
    async def get(self, id: str) -> Optional[T]:
        """Get a record by ID.
        
        Args:
            id: Record ID
            
        Returns:
            Record if found, None otherwise
            
        Raises:
            TranscriboError: If database operation fails
        """
        try:
            result = await self.session.get(self.model_class, id)
            return cast(Optional[T], result)
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get",
                "resource_id": id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e), "model": self.model_class.__name__}
            }
            log_error(f"Error getting {self.model_class.__name__} {id}: {str(e)}")
            raise TranscriboError(
                f"Failed to get {self.model_class.__name__}",
                details=error_context
            )
            
    @track_time(DB_OPERATION_DURATION)
    async def get_or_404(self, id: str) -> T:
        """Get a record by ID or raise 404.
        
        Args:
            id: Record ID
            
        Returns:
            Record if found
            
        Raises:
            ResourceNotFoundError: If record not found
            TranscriboError: If database operation fails
        """
        result = await self.get(id)
        if not result:
            error_context: ErrorContext = {
                "operation": "get_or_404",
                "resource_id": id,
                "timestamp": datetime.utcnow(),
                "details": {"model": self.model_class.__name__}
            }
            raise ResourceNotFoundError(
                self.model_class.__name__.lower(),
                id,
                details=error_context
            )
        return result
        
    @track_time(DB_OPERATION_DURATION)
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        order_by: Optional[str] = None
    ) -> List[T]:
        """List records with optional filtering.
        
        Args:
            filters: Optional filter conditions
            limit: Maximum number of records
            offset: Number of records to skip
            order_by: Optional order by column
            
        Returns:
            List of records
            
        Raises:
            TranscriboError: If database operation fails
        """
        try:
            query: Select = select(self.model_class)
            
            # Apply filters
            if filters:
                conditions: List[BinaryExpression] = []
                for key, value in filters.items():
                    if hasattr(self.model_class, key):
                        conditions.append(getattr(self.model_class, key) == value)
                if conditions:
                    query = query.where(*conditions)
            
            # Apply ordering
            if order_by and hasattr(self.model_class, order_by):
                query = query.order_by(getattr(self.model_class, order_by))
                
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            result = await self.session.execute(query)
            return cast(List[T], list(result.scalars().all()))
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "list",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": self.model_class.__name__,
                    "filters": filters,
                    "limit": limit,
                    "offset": offset
                }
            }
            log_error(f"Error listing {self.model_class.__name__}: {str(e)}")
            raise TranscriboError(
                f"Failed to list {self.model_class.__name__}",
                details=error_context
            )
            
    @track_time(DB_OPERATION_DURATION)
    async def create(self, data: Dict[str, Any]) -> T:
        """Create a new record.
        
        Args:
            data: Record data
            
        Returns:
            Created record
            
        Raises:
            TranscriboError: If database operation fails
        """
        try:
            # Add timestamps
            data['created_at'] = datetime.utcnow()
            data['updated_at'] = datetime.utcnow()
            
            # Create instance
            instance = self.model_class(**data)
            
            # Save to database
            self.session.add(instance)
            await self.session.commit()
            await self.session.refresh(instance)
            
            return cast(T, instance)
            
        except Exception as e:
            await self.session.rollback()
            error_context: ErrorContext = {
                "operation": "create",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": self.model_class.__name__,
                    "data": data
                }
            }
            log_error(f"Error creating {self.model_class.__name__}: {str(e)}")
            raise TranscriboError(
                f"Failed to create {self.model_class.__name__}",
                details=error_context
            )
            
    @track_time(DB_OPERATION_DURATION)
    async def update(self, id: str, data: Dict[str, Any]) -> T:
        """Update a record.
        
        Args:
            id: Record ID
            data: Update data
            
        Returns:
            Updated record
            
        Raises:
            ResourceNotFoundError: If record not found
            TranscriboError: If database operation fails
        """
        try:
            # Get existing record
            instance = await self.get_or_404(id)
            
            # Update timestamp
            data['updated_at'] = datetime.utcnow()
            
            # Update attributes
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
                    
            # Save changes
            await self.session.commit()
            await self.session.refresh(instance)
            
            return cast(T, instance)
            
        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            error_context: ErrorContext = {
                "operation": "update",
                "resource_id": id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": self.model_class.__name__,
                    "data": data
                }
            }
            log_error(f"Error updating {self.model_class.__name__} {id}: {str(e)}")
            raise TranscriboError(
                f"Failed to update {self.model_class.__name__}",
                details=error_context
            )
            
    @track_time(DB_OPERATION_DURATION)
    async def delete(self, id: str) -> None:
        """Delete a record.
        
        Args:
            id: Record ID
            
        Raises:
            ResourceNotFoundError: If record not found
            TranscriboError: If database operation fails
        """
        try:
            # Get existing record
            instance = await self.get_or_404(id)
            
            # Delete record
            await self.session.delete(instance)
            await self.session.commit()
            
        except ResourceNotFoundError:
            raise
        except Exception as e:
            await self.session.rollback()
            error_context: ErrorContext = {
                "operation": "delete",
                "resource_id": id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": self.model_class.__name__
                }
            }
            log_error(f"Error deleting {self.model_class.__name__} {id}: {str(e)}")
            raise TranscriboError(
                f"Failed to delete {self.model_class.__name__}",
                details=error_context
            )
            
    async def execute_query(self, query: Select) -> List[T]:
        """Execute a custom query.
        
        Args:
            query: SQLAlchemy select query
            
        Returns:
            Query results
            
        Raises:
            TranscriboError: If database operation fails
        """
        try:
            result = await self.session.execute(query)
            return cast(List[T], list(result.scalars().all()))
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "execute_query",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "model": self.model_class.__name__,
                    "query": str(query)
                }
            }
            log_error(f"Error executing query: {str(e)}")
            raise TranscriboError(
                "Failed to execute query",
                details=error_context
            )
