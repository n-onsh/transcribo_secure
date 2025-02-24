from datetime import datetime
from pydantic import BaseModel, UUID4
from typing import Optional

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
