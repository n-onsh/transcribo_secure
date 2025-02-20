from datetime import datetime
from pydantic import BaseModel, UUID4
from typing import Optional, Dict, List
from enum import Enum

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(str, Enum):
    TRANSCRIPTION = "transcription"
    CLEANUP = "cleanup"

class TranscriptionOptions(BaseModel):
    vocabulary: Optional[List[str]] = None
    language: Optional[str] = None
    generate_srt: bool = True

class Job(BaseModel):
    job_id: UUID4
    file_id: UUID4
    user_id: str
    job_type: JobType
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: Optional[float] = 0.0
    metadata: Optional[Dict] = None
    options: Optional[TranscriptionOptions] = None

class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    progress: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict] = None