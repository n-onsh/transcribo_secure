"""Metrics collection and tracking."""

import time
import functools
from typing import Dict, Any, Optional, Callable
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    REGISTRY,
    CollectorRegistry
)

# Create custom registry
REGISTRY = CollectorRegistry()

# Operation metrics
DB_OPERATION_DURATION = Histogram(
    'transcribo_db_operation_duration_seconds',
    'Duration of database operations',
    ['operation'],
    registry=REGISTRY
)

API_REQUEST_DURATION = Histogram(
    'transcribo_api_request_duration_seconds',
    'Duration of API requests',
    ['method', 'endpoint'],
    registry=REGISTRY
)

# Error metrics
ERROR_COUNT = Counter(
    'transcribo_errors_total',
    'Total number of errors',
    ['type', 'status_code', 'operation'],
    registry=REGISTRY
)

# File metrics
FILE_UPLOAD_SIZE = Histogram(
    'transcribo_file_upload_size_bytes',
    'Size of uploaded files',
    ['type'],
    registry=REGISTRY
)

FILE_PROCESSING_TIME = Histogram(
    'transcribo_file_processing_duration_seconds',
    'Duration of file processing',
    ['operation'],
    registry=REGISTRY
)

# Job metrics
JOB_DURATION = Histogram(
    'transcribo_job_duration_seconds',
    'Duration of jobs',
    ['type', 'status'],
    registry=REGISTRY
)

JOB_STATUS = Counter(
    'transcribo_job_status_total',
    'Job status counts',
    ['status'],
    registry=REGISTRY
)

# ZIP metrics
ZIP_PROCESSING_TIME = Histogram(
    'transcribo_zip_processing_duration_seconds',
    'Duration of ZIP processing',
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
    registry=REGISTRY
)

ZIP_EXTRACTION_ERRORS = Counter(
    'transcribo_zip_extraction_errors_total',
    'Total number of ZIP extraction errors',
    registry=REGISTRY
)

ZIP_FILE_COUNT = Histogram(
    'transcribo_zip_file_count',
    'Number of files in ZIP archives',
    buckets=[1, 2, 5, 10, 20, 50, 100],
    registry=REGISTRY
)

ZIP_TOTAL_SIZE = Histogram(
    'transcribo_zip_total_size_bytes',
    'Total size of ZIP archives',
    buckets=[
        1024*1024,      # 1MB
        10*1024*1024,   # 10MB
        100*1024*1024,  # 100MB
        1024*1024*1024, # 1GB
        10*1024*1024*1024  # 10GB
    ],
    registry=REGISTRY
)

# Transcription metrics
TRANSCRIPTION_DURATION = Histogram(
    'transcribo_transcription_duration_seconds',
    'Duration of transcription processing',
    ['model', 'language'],
    registry=REGISTRY
)

TRANSCRIPTION_ACCURACY = Histogram(
    'transcribo_transcription_accuracy',
    'Transcription accuracy scores',
    ['model', 'language'],
    registry=REGISTRY
)

TRANSCRIPTION_ERRORS = Counter(
    'transcribo_transcription_errors_total',
    'Total number of transcription errors',
    ['type'],
    registry=REGISTRY
)

# Editor metrics
EDITOR_OPERATION_DURATION = Histogram(
    'transcribo_editor_operation_duration_seconds',
    'Duration of editor operations',
    ['operation'],
    registry=REGISTRY
)

EDITOR_ERRORS = Counter(
    'transcribo_editor_errors_total',
    'Total number of editor errors',
    ['type'],
    registry=REGISTRY
)

# Resource metrics
RESOURCE_USAGE = Gauge(
    'transcribo_resource_usage',
    'Resource usage metrics',
    ['resource', 'type'],
    registry=REGISTRY
)

# System metrics
SYSTEM_HEALTH = Gauge(
    'transcribo_system_health',
    'System health status',
    ['component'],
    registry=REGISTRY
)

def track_time(metric: Histogram, labels: Dict[str, str]) -> Callable:
    """Decorator to track operation timing.
    
    Args:
        metric: Histogram metric to record time in
        labels: Labels to apply to metric
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metric.labels(**labels).observe(duration)
                return result
            except Exception:
                duration = time.time() - start_time
                metric.labels(**labels).observe(duration)
                raise
        return wrapper
    return decorator

def track_error(
    error_type: str,
    status_code: int,
    operation: str
) -> None:
    """Track error occurrence.
    
    Args:
        error_type: Type of error
        status_code: HTTP status code
        operation: Operation where error occurred
    """
    ERROR_COUNT.labels(
        type=error_type,
        status_code=status_code,
        operation=operation
    ).inc()

def track_job_status(status: str) -> None:
    """Track job status change.
    
    Args:
        status: New job status
    """
    JOB_STATUS.labels(status=status).inc()

def track_job_duration(
    job_type: str,
    status: str,
    duration: float
) -> None:
    """Track job duration.
    
    Args:
        job_type: Type of job
        status: Final job status
        duration: Job duration in seconds
    """
    JOB_DURATION.labels(
        type=job_type,
        status=status
    ).observe(duration)

def track_file_upload(
    file_type: str,
    size: int
) -> None:
    """Track file upload.
    
    Args:
        file_type: Type of file
        size: File size in bytes
    """
    FILE_UPLOAD_SIZE.labels(type=file_type).observe(size)

def track_file_processing(
    operation: str,
    duration: float
) -> None:
    """Track file processing duration.
    
    Args:
        operation: Processing operation
        duration: Processing duration in seconds
    """
    FILE_PROCESSING_TIME.labels(operation=operation).observe(duration)

def track_zip_processing(duration: float) -> None:
    """Track ZIP processing duration.
    
    Args:
        duration: Processing duration in seconds
    """
    ZIP_PROCESSING_TIME.observe(duration)

def track_zip_error() -> None:
    """Track ZIP extraction error."""
    ZIP_EXTRACTION_ERRORS.inc()

def track_transcription(
    model: str,
    language: str,
    duration: float,
    accuracy: Optional[float] = None
) -> None:
    """Track transcription metrics.
    
    Args:
        model: Transcription model used
        language: Language of transcription
        duration: Processing duration in seconds
        accuracy: Optional accuracy score
    """
    TRANSCRIPTION_DURATION.labels(
        model=model,
        language=language
    ).observe(duration)
    
    if accuracy is not None:
        TRANSCRIPTION_ACCURACY.labels(
            model=model,
            language=language
        ).observe(accuracy)

def track_transcription_error(error_type: str) -> None:
    """Track transcription error.
    
    Args:
        error_type: Type of transcription error
    """
    TRANSCRIPTION_ERRORS.labels(type=error_type).inc()

def track_editor_operation(
    operation: str,
    duration: float
) -> None:
    """Track editor operation duration.
    
    Args:
        operation: Editor operation
        duration: Operation duration in seconds
    """
    EDITOR_OPERATION_DURATION.labels(operation=operation).observe(duration)

def track_editor_error(error_type: str) -> None:
    """Track editor error.
    
    Args:
        error_type: Type of editor error
    """
    EDITOR_ERRORS.labels(type=error_type).inc()

def track_resource_usage(
    resource: str,
    type: str,
    value: float
) -> None:
    """Track resource usage.
    
    Args:
        resource: Resource being measured
        type: Type of measurement
        value: Resource usage value
    """
    RESOURCE_USAGE.labels(
        resource=resource,
        type=type
    ).set(value)

def track_system_health(
    component: str,
    status: float
) -> None:
    """Track system health status.
    
    Args:
        component: System component
        status: Health status (0-1)
    """
    SYSTEM_HEALTH.labels(component=component).set(status)
