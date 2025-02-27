"""API response models."""

from typing import Generic, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel
from pydantic.generics import GenericModel
from datetime import datetime

T = TypeVar('T', bound=BaseModel)

class PaginationMetadata(BaseModel):
    """Pagination metadata."""
    total: int
    limit: int
    has_more: bool
    next_cursor: Optional[str] = None

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ApiResponse(GenericModel, Generic[T]):
    """Standard API response."""
    data: T
    meta: Dict[str, Any] = {}
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ApiListResponse(GenericModel, Generic[T]):
    """Standard API list response."""
    data: List[T]
    pagination: Optional[PaginationMetadata] = None
    meta: Dict[str, Any] = {}
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ApiErrorResponse(BaseModel):
    """Standard API error response."""
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class CursorParams(BaseModel):
    """Cursor pagination parameters."""
    cursor: Optional[str] = None
    limit: int = 100
    sort_field: str = "created_at"
    sort_direction: str = "desc"

    class Config:
        """Pydantic config."""
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

    @property
    def is_forward(self) -> bool:
        """Check if pagination direction is forward."""
        return self.sort_direction.lower() == "desc"

    @property
    def is_backward(self) -> bool:
        """Check if pagination direction is backward."""
        return not self.is_forward
