from prometheus_client import Counter, Histogram, Summary, Gauge
import functools
import time
import asyncio
from typing import Optional

# API Metrics
HTTP_REQUEST_DURATION = Histogram(
    'transcribo_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

HTTP_REQUESTS_TOTAL = Counter(
    'transcribo_http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status_code']
)

HTTP_ERROR_REQUESTS_TOTAL = Counter(
    'transcribo_http_error_requests_total',
    'Total number of HTTP requests resulting in errors',
    ['method', 'endpoint', 'error_type']
)

# Job Metrics
JOBS_TOTAL = Counter(
    'transcribo_jobs_total',
    'Total number of transcription jobs',
    ['status']
)

JOB_PROCESSING_DURATION = Histogram(
    'transcribo_job_processing_duration_seconds',
    'Time spent processing jobs',
    ['status'],
    buckets=[30, 60, 120, 300, 600, 1200, 1800]
)

JOB_QUEUE_SIZE = Gauge(
    'transcribo_job_queue_size',
    'Number of jobs in queue',
    ['priority']
)

JOB_RETRY_COUNT = Counter(
    'transcribo_job_retries_total',
    'Total number of job retries',
    ['status']
)

# Storage Metrics
STORAGE_OPERATION_DURATION = Histogram(
    'transcribo_storage_operation_duration_seconds',
    'Time spent on storage operations',
    ['operation_name', 'bucket_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

STORAGE_OPERATION_ERRORS = Counter(
    'transcribo_storage_operation_errors_total',
    'Total number of storage operation errors',
    ['operation_name', 'bucket_name', 'error_type'],
)

STORAGE_BYTES = Gauge(
    'transcribo_storage_bytes',
    'Total storage used in bytes',
    ['bucket_name']
)

# Database Metrics
DB_OPERATION_DURATION = Histogram(
    'transcribo_db_operation_duration_seconds',
    'Time spent on database operations',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0]
)

DB_OPERATION_ERRORS = Counter(
    'transcribo_db_operation_errors_total',
    'Total number of database operation errors',
    ['operation', 'error_type']
)

DB_CONNECTIONS = Gauge(
    'transcribo_db_connections',
    'Number of active database connections'
)

# Business Metrics
AUDIO_DURATION_TOTAL = Counter(
    'transcribo_audio_duration_seconds_total',
    'Total duration of processed audio in seconds'
)

TRANSCRIPTION_WORD_COUNT = Counter(
    'transcribo_transcription_words_total',
    'Total number of transcribed words'
)

VOCABULARY_SIZE = Gauge(
    'transcribo_vocabulary_size',
    'Size of custom vocabulary',
    ['user_id']
)

def track_time(metric: Histogram, labels: Optional[dict] = None):
    """Decorator to track time spent in a function using a Histogram"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                # Get bucket_type from args or kwargs
                bucket_type = kwargs.get('bucket_type')
                if bucket_type is None and args:
                    bucket_type = args[2]  # Assuming bucket_type is the 3rd argument
                
                # Update labels with actual bucket_type
                current_labels = labels.copy() if labels else {}
                if bucket_type and 'bucket_name' in current_labels and current_labels['bucket_name'] == 'unknown':
                    current_labels['bucket_name'] = bucket_type
                
                result = await func(self, *args, **kwargs)
                duration = time.time() - start_time
                if current_labels:
                    metric.labels(**current_labels).observe(duration)
                else:
                    metric.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                if current_labels:
                    metric.labels(**current_labels).observe(duration)
                else:
                    metric.observe(duration)
                raise e
        
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                # Get bucket_type from args or kwargs
                bucket_type = kwargs.get('bucket_type')
                if bucket_type is None and args:
                    bucket_type = args[2]  # Assuming bucket_type is the 3rd argument
                
                # Update labels with actual bucket_type
                current_labels = labels.copy() if labels else {}
                if bucket_type and 'bucket_name' in current_labels and current_labels['bucket_name'] == 'unknown':
                    current_labels['bucket_name'] = bucket_type
                
                result = func(self, *args, **kwargs)
                duration = time.time() - start_time
                if current_labels:
                    metric.labels(**current_labels).observe(duration)
                else:
                    metric.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                if current_labels:
                    metric.labels(**current_labels).observe(duration)
                else:
                    metric.observe(duration)
                raise e
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def track_errors(counter: Counter, labels: Optional[dict] = None):
    """Decorator to track errors using a Counter"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(self, *args, **kwargs):
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                # Get bucket_type from args or kwargs
                bucket_type = kwargs.get('bucket_type')
                if bucket_type is None and args:
                    bucket_type = args[2]  # Assuming bucket_type is the 3rd argument
                
                # Update labels with actual bucket_type and error type
                error_labels = labels.copy() if labels else {}
                if bucket_type and 'bucket_name' in error_labels and error_labels['bucket_name'] == 'unknown':
                    error_labels['bucket_name'] = bucket_type
                if error_labels.get('error_type') == 'unknown':
                    error_labels['error_type'] = e.__class__.__name__
                counter.labels(**error_labels).inc()
                raise
        
        @functools.wraps(func)
        def sync_wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                # Get bucket_type from args or kwargs
                bucket_type = kwargs.get('bucket_type')
                if bucket_type is None and args:
                    bucket_type = args[2]  # Assuming bucket_type is the 3rd argument
                
                # Update labels with actual bucket_type and error type
                error_labels = labels.copy() if labels else {}
                if bucket_type and 'bucket_name' in error_labels and error_labels['bucket_name'] == 'unknown':
                    error_labels['bucket_name'] = bucket_type
                if error_labels.get('error_type') == 'unknown':
                    error_labels['error_type'] = e.__class__.__name__
                counter.labels(**error_labels).inc()
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def update_gauge(gauge: Gauge, value: float, labels: Optional[dict] = None):
    """Update a Gauge metric with labels"""
    if labels:
        gauge.labels(**labels).set(value)
    else:
        gauge.set(value)

def increment_counter(counter: Counter, labels: Optional[dict] = None):
    """Increment a Counter metric with labels"""
    if labels:
        counter.labels(**labels).inc()
    else:
        counter.inc()
