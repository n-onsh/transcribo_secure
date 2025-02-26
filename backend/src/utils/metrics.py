"""Metrics configuration and utilities."""

from prometheus_client import Counter, Histogram, Gauge, Summary
from datetime import datetime
import functools
import time
import asyncio

# HTTP metrics
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "status_code"]
)

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"]
)

HTTP_ERROR_REQUESTS_TOTAL = Counter(
    "http_error_requests_total",
    "Total number of HTTP error requests",
    ["method", "endpoint", "error_type"]
)

# Storage metrics
STORAGE_OPERATION_DURATION = Histogram(
    "storage_operation_duration_seconds",
    "Duration of storage operations",
    ["operation_name", "bucket"]
)

STORAGE_BYTES = Gauge(
    "storage_bytes",
    "Storage usage in bytes",
    ["bucket"]
)

STORAGE_OPERATION_ERRORS = Counter(
    "storage_operation_errors_total",
    "Total number of storage operation errors",
    ["operation_name", "bucket", "error_type"]
)

# Worker metrics
WORKER_JOBS_ACTIVE = Counter(
    "worker_jobs_active",
    "Number of active jobs per worker",
    ["worker_id"]
)

WORKER_LOAD_PERCENT = Gauge(
    "worker_load_percent",
    "Worker load percentage",
    ["worker_id"]
)

WORKER_HEALTH_STATUS = Gauge(
    "worker_health_status",
    "Worker health status (0=failed, 1=healthy)",
    ["worker_id"]
)

WORKER_RECOVERY_COUNT = Counter(
    "worker_recovery_count",
    "Number of worker recoveries",
    ["worker_id"]
)

WORKER_FAILOVER_TIME = Histogram(
    "worker_failover_seconds",
    "Time taken for worker failover",
    ["worker_id"]
)

# ZIP metrics
ZIP_EXTRACTION_TIME = Histogram(
    "zip_extraction_seconds",
    "Time taken to extract ZIP file",
    ["status"]
)

ZIP_FILE_COUNT = Counter(
    "zip_files_total",
    "Total number of files in ZIP archives"
)

ZIP_TOTAL_SIZE = Counter(
    "zip_bytes_total",
    "Total size of files in ZIP archives"
)

ZIP_ERROR_COUNT = Counter(
    "zip_errors_total",
    "Total number of ZIP processing errors"
)

# API metrics
API_REQUEST_TIME = Histogram(
    "api_request_seconds",
    "API request processing time",
    ["endpoint", "method"]
)

API_ERROR_COUNT = Counter(
    "api_errors_total",
    "Total number of API errors",
    ["endpoint", "error_type"]
)

API_REQUEST_SIZE = Histogram(
    "api_request_bytes",
    "API request size in bytes",
    ["endpoint"]
)

# Database metrics
DB_OPERATION_DURATION = Histogram(
    "db_operation_duration_seconds",
    "Duration of database operations",
    ["operation"]
)

DB_OPERATION_ERRORS = Counter(
    "db_operation_errors_total",
    "Total number of database operation errors",
    ["operation", "error_type"]
)

DB_CONNECTIONS = Gauge(
    "db_connections",
    "Number of active database connections"
)

# Job metrics
JOBS_CREATED = Counter(
    "jobs_created_total",
    "Total number of jobs created",
    ["status"]
)

JOBS_COMPLETED = Counter(
    "jobs_completed_total",
    "Total number of jobs completed",
    ["status"]
)

JOB_PROCESSING_TIME = Histogram(
    "job_processing_seconds",
    "Job processing time in seconds",
    ["language"]
)

JOB_QUEUE_TIME = Histogram(
    "job_queue_seconds",
    "Job time in queue before processing",
    ["priority"]
)

# System metrics
SYSTEM_CPU_USAGE = Gauge(
    'transcribo_system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'transcribo_system_memory_usage_bytes',
    'System memory usage in bytes',
    ['type']  # used/total
)

SYSTEM_DISK_USAGE = Gauge(
    'transcribo_system_disk_usage_bytes',
    'System disk usage in bytes',
    ['type']  # used/total
)

def increment_counter(counter: Counter, labels: dict = None):
    """Increment a counter metric.
    
    Args:
        counter: The counter metric to increment
        labels: Optional dictionary of label values
    """
    if labels:
        counter.labels(**labels).inc()
    else:
        counter.inc()

def update_gauge(gauge: Gauge, value: float, labels: dict = None):
    """Update a gauge metric.
    
    Args:
        gauge: The gauge metric to update
        value: The new value
        labels: Optional dictionary of label values
    """
    if labels:
        gauge.labels(**labels).set(value)
    else:
        gauge.set(value)

def observe_histogram(histogram: Histogram, value: float, labels: dict = None):
    """Record a value in a histogram metric.
    
    Args:
        histogram: The histogram metric to update
        value: The value to record
        labels: Optional dictionary of label values
    """
    if labels:
        histogram.labels(**labels).observe(value)
    else:
        histogram.observe(value)

def track_time(histogram: Histogram, labels: dict = None):
    """Decorator to track execution time of a function.
    
    Args:
        histogram: The histogram metric to update
        labels: Optional dictionary of label values
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                observe_histogram(histogram, duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                observe_histogram(histogram, duration, error_labels)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                observe_histogram(histogram, duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                observe_histogram(histogram, duration, error_labels)
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def track_errors(counter: Counter, labels: dict = None):
    """Decorator to track errors in a function.
    
    Args:
        counter: The counter metric to increment on error
        labels: Optional dictionary of label values
    """
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                increment_counter(counter, error_labels)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                increment_counter(counter, error_labels)
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
