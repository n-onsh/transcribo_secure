"""Type definitions for the backend."""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel

class ErrorSeverity(str, Enum):
    """Error severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class RecoverySuggestion(BaseModel):
    """Recovery suggestion for errors."""
    action: str
    description: str
    code_example: Optional[str] = None

class EnhancedErrorContext(BaseModel):
    """Enhanced error context with recovery suggestions."""
    operation: str
    timestamp: datetime
    severity: ErrorSeverity = ErrorSeverity.ERROR
    resource_id: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None
    details: Dict[str, Any] = {}
    recovery_suggestions: List[RecoverySuggestion] = []
    error_category: Optional[str] = None
    is_retryable: bool = False
    retry_after: Optional[int] = None  # seconds

class ErrorCode(str, Enum):
    """Error codes for the application."""
    INTERNAL_ERROR = "internal_error"
    VALIDATION_ERROR = "validation_error"
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RESOURCE_EXISTS = "resource_exists"
    SERVICE_UNAVAILABLE = "service_unavailable"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DATABASE_ERROR = "database_error"
    DATABASE_UNAVAILABLE = "database_unavailable"
    STORAGE_ERROR = "storage_error"
    STORAGE_UNAVAILABLE = "storage_unavailable"
    ENCRYPTION_ERROR = "encryption_error"
    KEY_MANAGEMENT_ERROR = "key_management_error"
    TRANSCRIPTION_ERROR = "transcription_error"
    ZIP_ERROR = "zip_error"
    FILE_NOT_FOUND = "file_not_found"
    FILE_TOO_LARGE = "file_too_large"
    FILE_CORRUPTED = "file_corrupted"
    UNSUPPORTED_FILE_TYPE = "unsupported_file_type"
    QUOTA_EXCEEDED = "quota_exceeded"
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TOKEN_MISSING = "token_missing"

class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    code: ErrorCode
    message: str
    request_id: Optional[str] = None
    details: Dict[str, Any] = {}
    severity: ErrorSeverity = ErrorSeverity.ERROR
    recovery_suggestions: List[RecoverySuggestion] = []
    is_retryable: bool = False
    retry_after: Optional[int] = None

class JobStatus(str, Enum):
    """Job status values."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobStage(str, Enum):
    """Job processing stages."""
    UPLOADING = "uploading"
    EXTRACTING = "extracting"
    PROCESSING = "processing"
    COMPLETED = "completed"

class JobProgress(BaseModel):
    """Job progress information."""
    stage: JobStage
    percent: float
    overall_progress: float
    completed_stages: List[str] = []
    estimated_time: Optional[int] = None
    resource_usage: Optional[Dict[str, float]] = None

class JobOptions(BaseModel):
    """Job processing options."""
    language: str
    model: Optional[str] = None
    vocabulary: Optional[str] = None
    diarization: bool = False
    combine_files: bool = False
    file_pattern: Optional[str] = None

class JobMetrics(BaseModel):
    """Job performance metrics."""
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    error_count: int = 0
    retry_count: int = 0

class JobResult(BaseModel):
    """Job processing result."""
    job_id: str
    status: JobStatus
    progress: JobProgress
    options: JobOptions
    metrics: JobMetrics
    error: Optional[ErrorResponse] = None
    output_url: Optional[str] = None
    is_zip: bool = False
    sub_jobs: List[str] = []

class FileValidation(BaseModel):
    """File validation rules."""
    max_size: int
    types: List[str]
    hash_required: bool = True
    hash_algorithms: List[str] = ["sha256"]

class ValidationRules(BaseModel):
    """Validation rules for file uploads."""
    single_file: FileValidation
    zip_file: FileValidation

class LanguageSupport(BaseModel):
    """Language support information."""
    code: str
    name: str
    description: Optional[str] = None
    models: List[str] = []
    is_diarization_supported: bool = False

class HelpText(BaseModel):
    """Help text for UI components."""
    language: str
    file_types: str
    vocabulary: str
    diarization: str
    time_estimate: str
