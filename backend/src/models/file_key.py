from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel
from .base import BaseModelWithTimestamps

class FileKey(BaseModelWithTimestamps):
    """File key model"""
    file_id: UUID
    encrypted_key: bytes
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class FileKeyShare(BaseModelWithTimestamps):
    """File key share model"""
    file_id: UUID
    user_id: UUID
    encrypted_key: bytes
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class FileKeyCreate(BaseModel):
    """File key creation model"""
    file_id: UUID
    encrypted_key: bytes

class FileKeyShareCreate(BaseModel):
    """File key share creation model"""
    file_id: UUID
    user_id: UUID
    encrypted_key: bytes

class FileKeyUpdate(BaseModel):
    """File key update model"""
    encrypted_key: Optional[bytes] = None

class FileKeyShareUpdate(BaseModel):
    """File key share update model"""
    encrypted_key: Optional[bytes] = None
