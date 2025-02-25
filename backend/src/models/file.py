from datetime import datetime
from pydantic import BaseModel, UUID4, Field
from typing import Optional
from .job import JobStatus

class FileMetadata(BaseModel):
    """File metadata model"""
    file_id: UUID4
    owner_id: str  # Changed from user_id to owner_id for consistency
    file_name: str
    bucket_type: str  # Changed from file_type to bucket_type for consistency
    created_at: datetime
    size_bytes: int
    content_type: Optional[str] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

class FileResponse(BaseModel):
    """File response model"""
    id: str = Field(..., description="File/Job ID")
    name: str = Field(..., description="File name")
    status: JobStatus = Field(..., description="Current status")
    progress: float = Field(
        default=0.0,
        description="Upload/processing progress (0-100)",
        ge=0.0,
        le=100.0
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    error: Optional[str] = Field(None, description="Error message if failed")
