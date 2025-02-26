"""Job models for database and API."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from .sqlalchemy_base import SQLAlchemyBase
from .base import BaseModelWithTimestamps, APIResponse
from ..types import JobID, UserID, FileID, TagID, JSONValue

class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    EXTRACTING = "extracting"  # For ZIP files

class JobPriority(int, Enum):
    """Job priority enumeration."""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class JobModel(SQLAlchemyBase):
    """SQLAlchemy model for jobs."""
    
    # Core fields
    id: str = Column(String, primary_key=True)
    owner_id: str = Column(String, nullable=False)
    file_name: str = Column(String, nullable=False)
    file_size: int = Column(Integer, nullable=False)
    duration: Optional[float] = Column(Float, nullable=True)
    
    # Status and progress
    status: JobStatus = Column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    priority: JobPriority = Column(SQLEnum(JobPriority), nullable=False, default=JobPriority.NORMAL)
    progress: float = Column(Float, nullable=False, default=0.0)
    error: Optional[str] = Column(String, nullable=True)
    
    # Retry handling
    retry_count: int = Column(Integer, nullable=False, default=0)
    max_retries: int = Column(Integer, nullable=False, default=3)
    next_retry_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    
    # Completion tracking
    completed_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    cancelled_at: Optional[datetime] = Column(DateTime(timezone=True), nullable=True)
    
    # Time estimation
    estimated_time: Optional[float] = Column(Float, nullable=True)
    estimate_confidence: Optional[float] = Column(Float, nullable=True)
    
    # ZIP handling
    is_zip: bool = Column(Boolean, nullable=False, default=False)
    zip_progress: Optional[Dict[str, Any]] = Column(JSON, nullable=True)
    sub_jobs: Optional[List[str]] = Column(JSON, nullable=True)
    parent_job_id: Optional[str] = Column(String, ForeignKey('job_model.id'), nullable=True)
    
    # Relationships
    parent_job = relationship("JobModel", remote_side=[id], backref="child_jobs")

class JobOptions(BaseModel):
    """Job options for API requests."""
    vocabulary: Optional[List[str]] = Field(
        default=[],
        description="Custom vocabulary for transcription"
    )
    generate_srt: bool = Field(
        default=True,
        description="Whether to generate SRT subtitles"
    )
    language: str = Field(
        default="de",
        description="Language code for transcription"
    )
    priority: JobPriority = Field(
        default=JobPriority.NORMAL,
        description="Job priority level"
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retry attempts"
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        schema_extra = {
            "example": {
                "vocabulary": ["Zürich", "Kanton"],
                "generate_srt": True,
                "language": "de",
                "priority": 1,
                "max_retries": 3
            }
        }

class JobProgress(BaseModel):
    """Job progress information."""
    stage: str = Field(
        ...,
        description="Current processing stage"
    )
    percent: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Progress percentage"
    )
    message: Optional[str] = Field(
        None,
        description="Progress message"
    )
    files_processed: Optional[int] = Field(
        None,
        description="Number of files processed (for ZIP jobs)"
    )
    total_files: Optional[int] = Field(
        None,
        description="Total number of files (for ZIP jobs)"
    )
    current_file: Optional[str] = Field(
        None,
        description="Currently processing file (for ZIP jobs)"
    )

    @validator('percent')
    def round_percent(cls, v: float) -> float:
        """Round percentage to 2 decimal places."""
        return round(v, 2)

class JobCreate(BaseModel):
    """Job creation request."""
    file_name: str = Field(
        ...,
        description="Name of the file to process"
    )
    file_size: int = Field(
        ...,
        gt=0,
        description="Size of the file in bytes"
    )
    owner_id: UserID = Field(
        ...,
        description="ID of the job owner"
    )
    options: Optional[JobOptions] = Field(
        default_factory=JobOptions,
        description="Job processing options"
    )

class JobUpdate(BaseModel):
    """Job update request."""
    status: Optional[JobStatus] = Field(
        None,
        description="New job status"
    )
    progress: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Progress percentage"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if job failed"
    )
    metadata: Optional[Dict[str, JSONValue]] = Field(
        None,
        description="Additional metadata"
    )

class JobResponse(BaseModelWithTimestamps):
    """Job response model."""
    id: JobID = Field(
        ...,
        description="Job ID"
    )
    owner_id: UserID = Field(
        ...,
        description="Owner ID"
    )
    file_name: str = Field(
        ...,
        description="File name"
    )
    file_size: int = Field(
        ...,
        description="File size in bytes"
    )
    status: JobStatus = Field(
        ...,
        description="Job status"
    )
    progress: float = Field(
        ...,
        description="Progress percentage"
    )
    priority: JobPriority = Field(
        ...,
        description="Job priority"
    )
    error: Optional[str] = Field(
        None,
        description="Error message if failed"
    )
    duration: Optional[float] = Field(
        None,
        description="Audio duration in seconds"
    )
    estimated_time: Optional[float] = Field(
        None,
        description="Estimated processing time in seconds"
    )
    estimate_confidence: Optional[float] = Field(
        None,
        description="Confidence in time estimate (0-1)"
    )
    is_zip: bool = Field(
        ...,
        description="Whether this is a ZIP job"
    )
    zip_progress: Optional[JobProgress] = Field(
        None,
        description="ZIP processing progress"
    )
    sub_jobs: Optional[List[JobID]] = Field(
        None,
        description="Sub-job IDs for ZIP jobs"
    )
    parent_job_id: Optional[JobID] = Field(
        None,
        description="Parent job ID for sub-jobs"
    )
    options: JobOptions = Field(
        ...,
        description="Job options"
    )
    metadata: Optional[Dict[str, JSONValue]] = Field(
        None,
        description="Additional metadata"
    )

    class Config:
        """Pydantic model configuration."""
        use_enum_values = True
        schema_extra = {
            "example": {
                "id": "job_123",
                "owner_id": "user_123",
                "file_name": "audio.mp3",
                "file_size": 1024000,
                "status": "processing",
                "progress": 45.5,
                "priority": 1,
                "duration": 300.5,
                "estimated_time": 150.0,
                "estimate_confidence": 0.85,
                "is_zip": False,
                "created_at": "2024-02-26T18:26:47Z",
                "updated_at": "2024-02-26T18:26:47Z",
                "options": {
                    "vocabulary": ["Zürich"],
                    "generate_srt": True,
                    "language": "de",
                    "priority": 1,
                    "max_retries": 3
                }
            }
        }

# Type aliases for responses
JobCreateResponse = APIResponse[JobResponse]
JobUpdateResponse = APIResponse[JobResponse]
JobListResponse = APIResponse[List[JobResponse]]
