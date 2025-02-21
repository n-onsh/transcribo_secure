from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime

class ErrorResponse(BaseModel):
    """Base model for error responses"""
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
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details",
        example={"field": "email", "reason": "invalid format"}
    )

class PaginatedResponse(BaseModel):
    """Base model for paginated responses"""
    items: List[Any] = Field(
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
        example=1
    )
    size: int = Field(
        ...,
        description="Number of items per page",
        example=20
    )

class BaseModelWithTimestamps(BaseModel):
    """Base model with created_at and updated_at fields"""
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

    def update_timestamp(self):
        """Update the updated_at timestamp"""
        self.updated_at = datetime.utcnow()
