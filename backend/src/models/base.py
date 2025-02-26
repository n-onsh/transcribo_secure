"""Base model classes."""

from typing import Optional, Any, Dict, List, TypeVar, Generic, cast
from datetime import datetime
from pydantic import BaseModel, Field
from pydantic.generics import GenericModel
from ..types import JSON, JSONValue, ErrorContext

T = TypeVar('T')

class ErrorResponse(BaseModel):
    """Base model for error responses."""
    code: str = Field(
        ...,
        description="Error code for programmatic handling",
        example="VALIDATION_ERROR"
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        example="Invalid input data"
    )
    details: Optional[ErrorContext] = Field(
        None,
        description="Additional error details",
        example={
            "operation": "validate_input",
            "resource_id": "user_123",
            "timestamp": "2024-02-26T18:26:47Z",
            "details": {"field": "email", "reason": "invalid format"}
        }
    )
    help_url: Optional[str] = Field(
        None,
        description="URL to documentation about this error",
        example="https://docs.example.com/errors/validation-error"
    )
    request_id: Optional[str] = Field(
        None,
        description="Unique identifier for tracking this error",
        example="abcd-1234-efgh-5678"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this error occurred",
        example="2024-02-26T18:26:47Z"
    )

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        schema_extra = {
            "example": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "details": {
                    "operation": "validate_input",
                    "resource_id": "user_123",
                    "timestamp": "2024-02-26T18:26:47Z",
                    "details": {"field": "email", "reason": "invalid format"}
                },
                "help_url": "https://docs.example.com/errors/validation-error",
                "request_id": "abcd-1234-efgh-5678",
                "timestamp": "2024-02-26T18:26:47Z"
            }
        }

class PaginatedResponse(GenericModel, Generic[T]):
    """Base model for paginated responses."""
    items: List[T] = Field(
        ...,
        description="List of items in the current page"
    )
    total: int = Field(
        ...,
        description="Total number of items",
        example=100
    )
    page: int = Field(
        ...,
        description="Current page number",
        example=1,
        ge=1
    )
    size: int = Field(
        ...,
        description="Number of items per page",
        example=20,
        gt=0
    )
    has_next: bool = Field(
        default=False,
        description="Whether there are more pages"
    )
    has_prev: bool = Field(
        default=False,
        description="Whether there are previous pages"
    )
    total_pages: int = Field(
        ...,
        description="Total number of pages",
        example=5,
        ge=1
    )

    @classmethod
    def create(
        cls,
        items: List[T],
        total: int,
        page: int,
        size: int
    ) -> 'PaginatedResponse[T]':
        """Create a paginated response.
        
        Args:
            items: List of items for the current page
            total: Total number of items
            page: Current page number
            size: Number of items per page
            
        Returns:
            Paginated response instance
        """
        total_pages = (total + size - 1) // size
        return cls(
            items=items,
            total=total,
            page=page,
            size=size,
            has_next=page < total_pages,
            has_prev=page > 1,
            total_pages=total_pages
        )

    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "items": ["item1", "item2", "item3"],
                "total": 100,
                "page": 1,
                "size": 20,
                "has_next": True,
                "has_prev": False,
                "total_pages": 5
            }
        }

class BaseModelWithTimestamps(BaseModel):
    """Base model with created_at and updated_at fields."""
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the record was created",
        example="2024-02-21T08:24:02Z"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the record was last updated",
        example="2024-02-21T08:24:02Z"
    )

    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.utcnow()

    class Config:
        """Pydantic model configuration."""
        json_encoders = {
            datetime: lambda dt: dt.isoformat()
        }
        schema_extra = {
            "example": {
                "created_at": "2024-02-21T08:24:02Z",
                "updated_at": "2024-02-21T08:24:02Z"
            }
        }

class APIResponse(GenericModel, Generic[T]):
    """Base model for API responses."""
    success: bool = Field(
        ...,
        description="Whether the operation was successful",
        example=True
    )
    data: Optional[T] = Field(
        None,
        description="Response data"
    )
    message: Optional[str] = Field(
        None,
        description="Response message",
        example="Operation completed successfully"
    )
    metadata: Optional[Dict[str, JSONValue]] = Field(
        None,
        description="Additional metadata"
    )

    @classmethod
    def success_response(
        cls,
        data: Optional[T] = None,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, JSONValue]] = None
    ) -> 'APIResponse[T]':
        """Create a success response.
        
        Args:
            data: Response data
            message: Response message
            metadata: Additional metadata
            
        Returns:
            Success response instance
        """
        return cls(
            success=True,
            data=data,
            message=message or "Operation completed successfully",
            metadata=metadata
        )

    @classmethod
    def error_response(
        cls,
        message: str,
        metadata: Optional[Dict[str, JSONValue]] = None
    ) -> 'APIResponse[T]':
        """Create an error response.
        
        Args:
            message: Error message
            metadata: Additional metadata
            
        Returns:
            Error response instance
        """
        return cls(
            success=False,
            message=message,
            metadata=metadata
        )

    class Config:
        """Pydantic model configuration."""
        schema_extra = {
            "example": {
                "success": True,
                "data": {"id": 1, "name": "example"},
                "message": "Operation completed successfully",
                "metadata": {"timestamp": "2024-02-26T18:26:47Z"}
            }
        }
