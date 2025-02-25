from enum import Enum, IntEnum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, validator, constr
from datetime import datetime, timedelta
import uuid
from .base import BaseModelWithTimestamps, ErrorResponse

# Custom types
FileName = constr(min_length=1, max_length=255)

class TranscriptionOptions(BaseModel):
    """Configuration options for transcription processing"""
    vocabulary: Optional[List[str]] = Field(
        default_factory=list,
        description="Custom vocabulary words to improve recognition",
        example=["Kubernetes", "FastAPI", "PostgreSQL"]
    )
    generate_srt: bool = Field(
        default=True,
        description="Whether to generate SRT subtitle file",
        example=True
    )
    language: Optional[str] = Field(
        default="de",
        description="Target language for transcription (ISO 639-1 code)",
        example="de"
    )
    supported_languages: List[str] = Field(
        default=["de", "en", "fr", "it"],
        description="List of supported languages",
        example=["de", "en", "fr", "it"]
    )

    @validator("language")
    def validate_language(cls, v, values):
        """Validate language is supported"""
        if v and values.get("supported_languages") and v not in values["supported_languages"]:
            raise ValueError(f"Language {v} not in supported languages: {values['supported_languages']}")
        return v

class JobPriority(IntEnum):
    """Priority levels for job processing"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

    @classmethod
    def get_description(cls, value: int) -> str:
        """Get human-readable description of priority level"""
        descriptions = {
            cls.LOW: "Background processing, no urgency",
            cls.NORMAL: "Standard processing priority",
            cls.HIGH: "Expedited processing",
            cls.URGENT: "Immediate processing required"
        }
        return descriptions.get(value, "Unknown priority")

class JobStatus(str, Enum):
    """Possible states of a transcription job"""
    PENDING = "pending"      # Job is queued for processing
    PROCESSING = "processing"  # Job is currently being processed
    COMPLETED = "completed"   # Job has finished successfully
    FAILED = "failed"        # Job encountered an error
    CANCELLED = "cancelled"   # Job was cancelled by user

    @classmethod
    def get_description(cls, value: str) -> str:
        """Get human-readable description of status"""
        descriptions = {
            cls.PENDING: "Waiting to be processed",
            cls.PROCESSING: "Currently being transcribed",
            cls.COMPLETED: "Transcription completed successfully",
            cls.FAILED: "Failed to complete transcription",
            cls.CANCELLED: "Transcription cancelled by user"
        }
        return descriptions.get(value, "Unknown status")

class Speaker(BaseModel):
    """Represents a speaker in the transcription"""
    name: str = Field(
        default="",
        description="Name or identifier of the speaker",
        example="Speaker 1"
    )
    language: Optional[str] = Field(
        default=None,
        description="Primary language of the speaker",
        example="en-US"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score of speaker identification",
        ge=0.0,
        le=1.0,
        example=0.95
    )

class Segment(BaseModel):
    """Represents a segment of transcribed speech"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the segment"
    )
    start: float = Field(
        ...,
        description="Start time of the segment in seconds",
        ge=0.0,
        example=10.5
    )
    end: float = Field(
        ...,
        description="End time of the segment in seconds",
        ge=0.0,
        example=15.7
    )
    text: str = Field(
        ...,
        description="Transcribed text for this segment",
        example="Hello, welcome to the meeting."
    )
    speaker_idx: int = Field(
        ...,
        description="Index of the speaker in speakers array",
        ge=0,
        example=0
    )
    is_foreign_language: bool = Field(
        default=False,
        description="Whether this segment is in a different language",
        example=False
    )
    language: Optional[str] = Field(
        default=None,
        description="Detected language code for this segment",
        example="en-US"
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score of the transcription",
        ge=0.0,
        le=1.0,
        example=0.92
    )
    words: Optional[List[Dict]] = Field(
        default_factory=list,
        description="Word-level timing and confidence information"
    )

    @validator("end")
    def validate_end_time(cls, v, values):
        """Validate end time is after start time"""
        if "start" in values and v <= values["start"]:
            raise ValueError("End time must be after start time")
        return v

class Transcription(BaseModel):
    """Complete transcription result"""
    speakers: List[Speaker] = Field(
        default_factory=list,
        description="List of speakers in the transcription"
    )
    segments: List[Segment] = Field(
        default_factory=list,
        description="List of transcribed segments"
    )
    language: Optional[str] = Field(
        default=None,
        description="Primary language of the transcription",
        example="en-US"
    )
    duration: Optional[float] = Field(
        default=None,
        description="Total duration in seconds",
        ge=0.0,
        example=120.5
    )
    word_count: Optional[int] = Field(
        default=None,
        description="Total number of words",
        ge=0,
        example=250
    )
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional metadata about the transcription"
    )

class Job(BaseModelWithTimestamps):
    """Transcription job"""
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier for the job"
    )
    owner_id: str = Field(
        ...,
        description="ID of the user who owns the job",
        example="user123"
    )
    file_name: FileName = Field(
        ...,
        description="Name of the audio/video file",
        example="meeting-2024-02-21.mp4"
    )
    options: TranscriptionOptions = Field(
        default_factory=TranscriptionOptions,
        description="Transcription configuration options"
    )
    file_size: int = Field(
        ...,
        description="Size of the file in bytes",
        gt=0,
        example=1048576
    )
    duration: Optional[float] = Field(
        default=None,
        description="Duration of the media in seconds",
        ge=0.0,
        example=300.5
    )
    status: JobStatus = Field(
        default=JobStatus.PENDING,
        description="Current status of the job"
    )
    priority: JobPriority = Field(
        default=JobPriority.NORMAL,
        description="Processing priority of the job"
    )
    progress: float = Field(
        default=0.0,
        description="Processing progress (0-100)",
        ge=0.0,
        le=100.0,
        example=45.5
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if job failed",
        example="Failed to process audio: Invalid format"
    )
    retry_count: int = Field(
        default=0,
        description="Number of retry attempts",
        ge=0,
        example=1
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts",
        gt=0,
        example=3
    )
    next_retry_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp for next retry attempt"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when job completed"
    )
    cancelled_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when job was cancelled"
    )
    estimated_time: Optional[float] = Field(
        default=None,
        description="Estimated processing time in seconds",
        ge=0.0,
        example=300.0
    )
    estimated_range: Optional[tuple[float, float]] = Field(
        default=None,
        description="Range of estimated processing time (min, max) in seconds",
        example=(240.0, 360.0)
    )
    estimate_confidence: Optional[float] = Field(
        default=None,
        description="Confidence level of time estimate (0-1)",
        ge=0.0,
        le=1.0,
        example=0.8
    )
    metadata: Dict = Field(
        default_factory=dict,
        description="Additional metadata about the job"
    )

    @validator("estimated_range")
    def validate_estimated_range(cls, v):
        """Validate estimated range is valid"""
        if v is not None:
            if len(v) != 2:
                raise ValueError("Estimated range must have exactly 2 values")
            if v[0] > v[1]:
                raise ValueError("Minimum estimate must be less than maximum")
            if v[0] < 0 or v[1] < 0:
                raise ValueError("Estimates must be non-negative")
        return v

    @validator("estimate_confidence")
    def validate_estimate_confidence(cls, v):
        """Validate estimate confidence is between 0 and 1"""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Estimate confidence must be between 0 and 1")
        return v

    @validator("priority")
    def validate_priority(cls, v):
        """Validate priority is within enum range"""
        if not isinstance(v, JobPriority):
            try:
                return JobPriority(int(v))
            except (ValueError, TypeError):
                raise ValueError("Invalid priority value")
        return v

    @validator("retry_count")
    def validate_retry_count(cls, v):
        """Validate retry count is non-negative"""
        if v < 0:
            raise ValueError("Retry count must be non-negative")
        return v

    @validator("max_retries")
    def validate_max_retries(cls, v):
        """Validate max retries is positive"""
        if v < 1:
            raise ValueError("Max retries must be positive")
        return v

    def update_progress(self, progress: float):
        """Update job progress"""
        self.progress = min(max(progress, 0.0), 100.0)
        self.updated_at = datetime.utcnow()

    def complete(self):
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        self.progress = 100.0
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.next_retry_at = None

    def fail(self, error: str):
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()
        
        # Schedule retry if attempts remain
        if self.retry_count < self.max_retries:
            self.retry_count += 1
            # Exponential backoff: 2^retry_count minutes
            delay = 2 ** self.retry_count
            self.next_retry_at = datetime.utcnow() + timedelta(minutes=delay)
            self.status = JobStatus.PENDING
        else:
            self.next_retry_at = None

    def start_processing(self):
        """Mark job as processing"""
        self.status = JobStatus.PROCESSING
        self.progress = 0.0
        self.updated_at = datetime.utcnow()
        self.next_retry_at = None

    def cancel(self):
        """Cancel the job"""
        self.status = JobStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self.next_retry_at = None

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return (
            self.status == JobStatus.FAILED and
            self.retry_count < self.max_retries and
            (
                self.next_retry_at is None or
                datetime.utcnow() >= self.next_retry_at
            )
        )

    def should_process(self) -> bool:
        """Check if job should be processed"""
        return (
            self.status == JobStatus.PENDING and
            (
                self.next_retry_at is None or
                datetime.utcnow() >= self.next_retry_at
            )
        )

class JobUpdate(BaseModel):
    """Job update model"""
    status: Optional[JobStatus] = None
    progress: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None

    def apply_to(self, job: Job):
        """Apply update to job"""
        if self.status is not None:
            job.status = self.status
        if self.progress is not None:
            job.update_progress(self.progress)
        if self.error is not None:
            job.error = self.error
        if self.metadata is not None:
            job.metadata.update(self.metadata)
        job.updated_at = datetime.utcnow()

class TranscriptionUpdate(BaseModel):
    """Transcription update model"""
    speakers: Optional[List[Speaker]] = None
    segments: Optional[List[Segment]] = None
    metadata: Optional[Dict] = None

    def apply_to(self, transcription: Transcription):
        """Apply update to transcription"""
        if self.speakers is not None:
            transcription.speakers = self.speakers
        if self.segments is not None:
            transcription.segments = self.segments
        if self.metadata is not None:
            transcription.metadata.update(self.metadata)

class JobFilter(BaseModel):
    """Job filter model"""
    user_id: Optional[str] = None
    status: Optional[JobStatus] = None
    priority: Optional[JobPriority] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    file_name: Optional[str] = None
    retry_count: Optional[int] = None
    language: Optional[str] = None

    def apply(self, jobs: List[Job]) -> List[Job]:
        """Apply filter to jobs"""
        filtered = jobs
        
        if self.user_id:
            filtered = [j for j in filtered if j.owner_id == self.user_id]
            
        if self.status:
            filtered = [j for j in filtered if j.status == self.status]
            
        if self.priority:
            filtered = [j for j in filtered if j.priority == self.priority]
            
        if self.created_after:
            filtered = [j for j in filtered if j.created_at >= self.created_after]
            
        if self.created_before:
            filtered = [j for j in filtered if j.created_at <= self.created_before]
            
        if self.file_name:
            filtered = [j for j in filtered if self.file_name.lower() in j.file_name.lower()]
            
        if self.retry_count is not None:
            filtered = [j for j in filtered if j.retry_count == self.retry_count]
            
        if self.language:
            filtered = [j for j in filtered if j.options.language == self.language]
            
        return filtered

class JobSort(BaseModel):
    """Job sort model"""
    field: str = Field(default="priority")
    ascending: bool = Field(default=False)

    def apply(self, jobs: List[Job]) -> List[Job]:
        """Apply sort to jobs"""
        # Sort by priority first (if not explicitly sorting by another field)
        if self.field != "priority":
            jobs = sorted(jobs, key=lambda j: j.priority, reverse=True)
        
        # Then apply requested sort
        return sorted(
            jobs,
            key=lambda j: getattr(j, self.field),
            reverse=not self.ascending
        )
