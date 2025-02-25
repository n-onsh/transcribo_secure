"""Metrics configuration."""

from opentelemetry.metrics import get_meter
from datetime import datetime

meter = get_meter(__name__)

# Storage operation metrics
STORAGE_OPERATION_DURATION = meter.create_histogram(
    "storage_operation_duration_seconds",
    "Duration of storage operations",
    ["operation_name", "bucket"]
)

STORAGE_BYTES = meter.create_gauge(
    "storage_bytes",
    "Storage usage in bytes",
    ["bucket"]
)

# Database operation metrics
DB_OPERATION_DURATION = meter.create_histogram(
    "db_operation_duration_seconds",
    "Duration of database operations",
    ["operation"]
)

DB_OPERATION_ERRORS = meter.create_counter(
    "db_operation_errors_total",
    "Total number of database operation errors",
    ["operation", "error_type"]
)

DB_CONNECTIONS = meter.create_gauge(
    "db_connections",
    "Number of active database connections"
)

# Job metrics
JOBS_CREATED = meter.create_counter(
    "jobs_created_total",
    "Total number of jobs created",
    ["status"]
)

JOBS_COMPLETED = meter.create_counter(
    "jobs_completed_total",
    "Total number of jobs completed",
    ["status"]
)

JOB_PROCESSING_TIME = meter.create_histogram(
    "job_processing_seconds",
    "Job processing time in seconds",
    ["language"]
)

JOB_QUEUE_TIME = meter.create_histogram(
    "job_queue_seconds",
    "Job time in queue before processing",
    ["priority"]
)

# Worker metrics
WORKER_JOBS_ACTIVE = meter.create_counter(
    "worker_jobs_active",
    "Number of active jobs per worker",
    ["worker_id"]
)

WORKER_LOAD_PERCENT = meter.create_gauge(
    "worker_load_percent",
    "Worker load percentage",
    ["worker_id"]
)

WORKER_HEALTH_STATUS = meter.create_gauge(
    "worker_health_status",
    "Worker health status (0=failed, 1=healthy)",
    ["worker_id"]
)

WORKER_RECOVERY_COUNT = meter.create_counter(
    "worker_recovery_count",
    "Number of worker recoveries",
    ["worker_id"]
)

WORKER_FAILOVER_TIME = meter.create_histogram(
    "worker_failover_seconds",
    "Time taken for worker failover",
    ["worker_id"]
)

# ZIP metrics
ZIP_EXTRACTION_TIME = meter.create_histogram(
    "zip_extraction_seconds",
    "Time taken to extract ZIP file",
    ["status"]
)

ZIP_FILE_COUNT = meter.create_counter(
    "zip_files_total",
    "Total number of files in ZIP archives",
)

ZIP_TOTAL_SIZE = meter.create_counter(
    "zip_bytes_total",
    "Total size of files in ZIP archives",
)

ZIP_ERROR_COUNT = meter.create_counter(
    "zip_errors_total",
    "Total number of ZIP processing errors",
    ["error_type"]
)

ZIP_VALIDATION_TIME = meter.create_histogram(
    "zip_validation_seconds",
    "Time taken to validate ZIP file",
    ["result"]
)

ZIP_CLEANUP_TIME = meter.create_histogram(
    "zip_cleanup_seconds",
    "Time taken to clean up after ZIP processing",
    ["status"]
)

# Storage metrics
STORAGE_UPLOAD_TIME = meter.create_histogram(
    "storage_upload_seconds",
    "Time taken to upload file to storage",
    ["status"]
)

STORAGE_DOWNLOAD_TIME = meter.create_histogram(
    "storage_download_seconds",
    "Time taken to download file from storage",
    ["status"]
)

STORAGE_OPERATION_ERRORS = meter.create_counter(
    "storage_errors_total",
    "Total number of storage operation errors",
    ["operation", "error_type"]
)

# Database metrics
DB_QUERY_TIME = meter.create_histogram(
    "db_query_seconds",
    "Database query execution time",
    ["query_type"]
)

DB_CONNECTION_ERRORS = meter.create_counter(
    "db_connection_errors_total",
    "Total number of database connection errors",
)

DB_DEADLOCK_COUNT = meter.create_counter(
    "db_deadlocks_total",
    "Total number of database deadlocks",
)

# Cache metrics
CACHE_HIT_COUNT = meter.create_counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["cache_type"]
)

CACHE_MISS_COUNT = meter.create_counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["cache_type"]
)

CACHE_EVICTION_COUNT = meter.create_counter(
    "cache_evictions_total",
    "Total number of cache evictions",
    ["cache_type"]
)

# API metrics
API_REQUEST_TIME = meter.create_histogram(
    "api_request_seconds",
    "API request processing time",
    ["endpoint", "method"]
)

API_ERROR_COUNT = meter.create_counter(
    "api_errors_total",
    "Total number of API errors",
    ["endpoint", "error_type"]
)

API_REQUEST_SIZE = meter.create_histogram(
    "api_request_bytes",
    "API request size in bytes",
    ["endpoint"]
)

# System metrics
SYSTEM_MEMORY_USAGE = meter.create_gauge(
    "system_memory_bytes",
    "System memory usage in bytes",
    ["type"]
)

SYSTEM_CPU_USAGE = meter.create_gauge(
    "system_cpu_percent",
    "System CPU usage percentage",
    ["type"]
)

SYSTEM_DISK_USAGE = meter.create_gauge(
    "system_disk_bytes",
    "System disk usage in bytes",
    ["path"]
)

def track_time(name: str, labels: dict):
    """Decorator to track execution time of a function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = datetime.utcnow()
            try:
                result = await func(*args, **kwargs)
                duration = (datetime.utcnow() - start).total_seconds()
                meter.create_histogram(
                    name,
                    "Function execution time",
                    labels
                ).record(duration)
                return result
            except Exception as e:
                duration = (datetime.utcnow() - start).total_seconds()
                meter.create_histogram(
                    name,
                    "Function execution time",
                    {**labels, "error": type(e).__name__}
                ).record(duration)
                raise
        return wrapper
    return decorator

def track_errors(name: str, labels: dict):
    """Decorator to track errors in a function."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                meter.create_counter(
                    name,
                    "Function error count",
                    {**labels, "error": type(e).__name__}
                ).inc()
                raise
        return wrapper
    return decorator

def update_gauge(gauge, value: float, labels: dict = None):
    """Update a gauge metric."""
    if labels:
        gauge.set(value, labels)
    else:
        gauge.set(value)
