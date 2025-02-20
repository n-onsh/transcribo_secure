from enum import Enum, IntEnum
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, validator
from datetime import datetime, timedelta
from datetime import datetime
import uuid

class TranscriptionOptions(BaseModel):
    """Transcription options model"""
    vocabulary: Optional[List[str]] = Field(default_factory=list)
    generate_srt: bool = Field(default=True)

class JobPriority(IntEnum):
    """Job priority enum"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class JobStatus(str, Enum):
    """Job status enum"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Speaker(BaseModel):
    """Speaker model"""
    name: str = Field(default="")
    language: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None)

class Segment(BaseModel):
    """Segment model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    start: float
    end: float
    text: str
    speaker_idx: int
    is_foreign_language: bool = Field(default=False)
    language: Optional[str] = Field(default=None)
    confidence: Optional[float] = Field(default=None)
    words: Optional[List[Dict]] = Field(default_factory=list)

class Transcription(BaseModel):
    """Transcription model"""
    speakers: List[Speaker] = Field(default_factory=list)
    segments: List[Segment] = Field(default_factory=list)
    language: Optional[str] = Field(default=None)
    duration: Optional[float] = Field(default=None)
    word_count: Optional[int] = Field(default=None)
    metadata: Dict = Field(default_factory=dict)

class Job(BaseModel):
    """Job model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    file_name: str
    file_size: int
    duration: Optional[float] = Field(default=None)
    status: JobStatus = Field(default=JobStatus.PENDING)
    priority: JobPriority = Field(default=JobPriority.NORMAL)
    progress: float = Field(default=0.0)
    error: Optional[str] = Field(default=None)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    next_retry_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    metadata: Dict = Field(default_factory=dict)

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

    def apply(self, jobs: List[Job]) -> List[Job]:
        """Apply filter to jobs"""
        filtered = jobs
        
        if self.user_id:
            filtered = [j for j in filtered if j.user_id == self.user_id]
            
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
