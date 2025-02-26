"""Tag models."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class Tag(BaseModel):
    """Tag model."""
    
    id: str = Field(..., description="Unique tag identifier")
    name: str = Field(..., description="Tag name")
    color: str = Field(..., description="Tag color (hex code)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    user_id: Optional[str] = Field(None, description="Owner user ID")
    metadata: Optional[Dict] = Field({}, description="Additional metadata")

class TagAssignment(BaseModel):
    """Tag assignment model."""
    
    id: str = Field(..., description="Unique assignment identifier")
    tag_id: str = Field(..., description="Tag ID")
    resource_id: str = Field(..., description="Resource ID (job, file, etc.)")
    resource_type: str = Field(..., description="Resource type ('job', 'file', etc.)")
    created_at: datetime = Field(..., description="Creation timestamp")
    user_id: Optional[str] = Field(None, description="User who created the assignment")
    metadata: Optional[Dict] = Field({}, description="Additional metadata")

class TagCreate(BaseModel):
    """Model for tag creation."""
    
    name: str = Field(..., description="Tag name")
    color: str = Field(..., description="Tag color (hex code)")
    metadata: Optional[Dict] = Field({}, description="Additional metadata")

class TagUpdate(BaseModel):
    """Model for tag updates."""
    
    name: Optional[str] = Field(None, description="Tag name")
    color: Optional[str] = Field(None, description="Tag color (hex code)")
    metadata: Optional[Dict] = Field(None, description="Additional metadata")

class TagResponse(BaseModel):
    """Tag response model."""
    
    id: str = Field(..., description="Tag ID")
    name: str = Field(..., description="Tag name")
    color: str = Field(..., description="Tag color (hex code)")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict = Field({}, description="Additional metadata")
