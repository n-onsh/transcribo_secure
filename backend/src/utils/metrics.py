from opentelemetry import metrics
import functools
import time
import asyncio
from typing import Optional

# Get meter
meter = metrics.get_meter_provider().get_meter("backend")

# API Metrics
http_request_duration = meter.create_histogram(
    "transcribo_backend_request_duration_seconds",
    description="HTTP request duration in seconds",
    unit="s"
)

http_requests_total = meter.create_counter(
    "transcribo_backend_requests_total",
    description="Total number of HTTP requests",
    unit="1"
)

http_error_requests_total = meter.create_counter(
    "transcribo_backend_error_requests_total",
    description="Total number of HTTP requests resulting in errors",
    unit="1"
)

# Job Metrics
jobs_total = meter.create_counter(
    "transcribo_backend_jobs_total",
    description="Total number of jobs by status",
    unit="1"
)

job_processing_duration = meter.create_histogram(
    "transcribo_backend_job_processing_duration_seconds",
    description="Time spent processing jobs",
    unit="s"
)

job_queue_size = meter.create_up_down_counter(
    "transcribo_backend_job_queue_size",
    description="Number of jobs in queue",
    unit="1"
)

job_retry_count = meter.create_counter(
    "transcribo_backend_job_retries_total",
    description="Total number of job retries",
    unit="1"
)

# Storage Metrics
storage_operation_duration = meter.create_histogram(
    "transcribo_backend_storage_operation_duration_seconds",
    description="Time spent on storage operations",
    unit="s"
)

storage_operation_errors = meter.create_counter(
    "transcribo_backend_storage_operation_errors_total",
    description="Total number of storage operation errors",
    unit="1"
)

storage_operations_total = meter.create_counter(
    "transcribo_backend_storage_operations_total",
    description="Total number of storage operations by type",
    unit="1"
)

# Database Metrics
db_operation_duration = meter.create_histogram(
    "transcribo_backend_db_operation_duration_seconds",
    description="Time spent on database operations",
    unit="s"
)

db_operation_errors = meter.create_counter(
    "transcribo_backend_db_operation_errors_total",
    description="Total number of database operation errors",
    unit="1"
)

db_connections = meter.create_up_down_counter(
    "transcribo_backend_db_connections",
    description="Number of active database connections",
    unit="1"
)

# Resource Metrics
memory_usage = meter.create_up_down_counter(
    "transcribo_backend_memory_bytes",
    description="Backend memory usage",
    unit="By"
)

cpu_usage = meter.create_up_down_counter(
    "transcribo_backend_cpu_usage_percent",
    description="Backend CPU usage percentage",
    unit="1"
)

def track_request(path_type: str, method: str, status_code: int, duration: float):
    """Track HTTP request metrics"""
    labels = {
        "path_type": path_type,  # Use generic path type instead of actual path
        "method": method,
        "status": str(status_code)
    }
    http_requests_total.add(1, labels)
    http_request_duration.record(duration, labels)
    if status_code >= 400:
        http_error_requests_total.add(1, labels)

def track_job(status: str):
    """Track job status"""
    jobs_total.add(1, {"status": status})

def track_job_processing(duration: float, success: bool):
    """Track job processing duration"""
    job_processing_duration.record(duration, {"status": "success" if success else "error"})

def track_job_queue(size: int):
    """Track job queue size"""
    job_queue_size.add(size)

def track_job_retry():
    """Track job retry"""
    job_retry_count.add(1)

def track_storage_operation(operation_type: str, duration: float, success: bool):
    """Track storage operation"""
    labels = {
        "operation_type": operation_type,
        "status": "success" if success else "error"
    }
    storage_operations_total.add(1, labels)
    storage_operation_duration.record(duration, labels)
    if not success:
        storage_operation_errors.add(1, labels)

def track_db_operation(operation_type: str, duration: float, success: bool):
    """Track database operation"""
    labels = {
        "operation_type": operation_type,
        "status": "success" if success else "error"
    }
    db_operation_duration.record(duration, labels)
    if not success:
        db_operation_errors.add(1, labels)

def track_db_connection_change(delta: int):
    """Track database connection changes"""
    db_connections.add(delta)

def track_resource_usage(memory: float, cpu: float):
    """Track resource usage"""
    memory_usage.add(memory)
    cpu_usage.add(cpu)

def track_time(metric, labels: Optional[dict] = None):
    """Decorator to track time spent in a function using a Histogram"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metric.record(duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_labels = {**labels, "status": "error"} if labels else {"status": "error"}
                metric.record(duration, error_labels)
                raise e
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                metric.record(duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_labels = {**labels, "status": "error"} if labels else {"status": "error"}
                metric.record(duration, error_labels)
                raise e
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def track_errors(counter, labels: Optional[dict] = None):
    """Decorator to track errors using a Counter"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_labels = labels.copy() if labels else {}
                error_labels["error_type"] = e.__class__.__name__
                counter.add(1, error_labels)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_labels = labels.copy() if labels else {}
                error_labels["error_type"] = e.__class__.__name__
                counter.add(1, error_labels)
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
