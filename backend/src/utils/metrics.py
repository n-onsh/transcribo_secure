"""Metrics utilities."""

from prometheus_client import Counter, Gauge, Histogram
from typing import Dict, Any

# Error metrics
ERROR_COUNT = Counter(
    "transcribo_errors_total",
    "Total number of errors",
    ["type"]
)

ERROR_SEVERITY = Counter(
    "transcribo_error_severity_total",
    "Error count by severity",
    ["type", "severity"]
)

ERROR_RETRY_COUNT = Counter(
    "transcribo_error_retries_total",
    "Number of error retries",
    ["type"]
)

ERROR_RECOVERY_TIME = Histogram(
    "transcribo_error_recovery_seconds",
    "Time taken to recover from errors",
    ["type"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600]
)

# Resource metrics
MEMORY_USAGE = Gauge(
    "transcribo_memory_bytes",
    "Memory usage in bytes",
    ["type"]
)

CPU_USAGE = Gauge(
    "transcribo_cpu_percent",
    "CPU usage percentage",
    ["type"]
)

STORAGE_USAGE = Gauge(
    "transcribo_storage_bytes",
    "Storage usage in bytes",
    ["type"]
)

# Operation metrics
OPERATION_DURATION = Histogram(
    "transcribo_operation_duration_seconds",
    "Time spent on operations",
    ["operation"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

OPERATION_FAILURES = Counter(
    "transcribo_operation_failures_total",
    "Number of failed operations",
    ["operation"]
)

OPERATION_SUCCESS = Counter(
    "transcribo_operation_success_total",
    "Number of successful operations",
    ["operation"]
)

# Queue metrics
QUEUE_SIZE = Gauge(
    "transcribo_queue_size",
    "Number of items in queue",
    ["queue"]
)

QUEUE_LATENCY = Histogram(
    "transcribo_queue_latency_seconds",
    "Time items spend in queue",
    ["queue"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600]
)

# Job metrics
JOB_DURATION = Histogram(
    "transcribo_job_duration_seconds",
    "Time spent processing jobs",
    ["type"],
    buckets=[1, 5, 15, 30, 60, 120, 300, 600, 1800, 3600]
)

JOB_STATUS = Counter(
    "transcribo_job_status_total",
    "Job completion status",
    ["type", "status"]
)

def track_error(error_type: str, severity: str):
    """Track error occurrence.
    
    Args:
        error_type: Type of error
        severity: Error severity level
    """
    ERROR_COUNT.labels(type=error_type).inc()
    ERROR_SEVERITY.labels(
        type=error_type,
        severity=severity
    ).inc()

def track_error_retry(error_type: str):
    """Track error retry attempt.
    
    Args:
        error_type: Type of error
    """
    ERROR_RETRY_COUNT.labels(type=error_type).inc()

def track_error_recovery(error_type: str, duration: float):
    """Track error recovery time.
    
    Args:
        error_type: Type of error
        duration: Recovery duration in seconds
    """
    ERROR_RECOVERY_TIME.labels(type=error_type).observe(duration)

def track_memory_usage(memory_type: str, bytes_used: int):
    """Track memory usage.
    
    Args:
        memory_type: Type of memory usage
        bytes_used: Memory usage in bytes
    """
    MEMORY_USAGE.labels(type=memory_type).set(bytes_used)

def track_cpu_usage(cpu_type: str, percent_used: float):
    """Track CPU usage.
    
    Args:
        cpu_type: Type of CPU usage
        percent_used: CPU usage percentage
    """
    CPU_USAGE.labels(type=cpu_type).set(percent_used)

def track_storage_usage(storage_type: str, bytes_used: int):
    """Track storage usage.
    
    Args:
        storage_type: Type of storage usage
        bytes_used: Storage usage in bytes
    """
    STORAGE_USAGE.labels(type=storage_type).set(bytes_used)

def track_operation_duration(operation: str, duration: float):
    """Track operation duration.
    
    Args:
        operation: Operation name
        duration: Duration in seconds
    """
    OPERATION_DURATION.labels(operation=operation).observe(duration)

def track_operation_result(operation: str, success: bool):
    """Track operation result.
    
    Args:
        operation: Operation name
        success: Whether operation succeeded
    """
    if success:
        OPERATION_SUCCESS.labels(operation=operation).inc()
    else:
        OPERATION_FAILURES.labels(operation=operation).inc()

def track_queue_size(queue: str, size: int):
    """Track queue size.
    
    Args:
        queue: Queue name
        size: Current queue size
    """
    QUEUE_SIZE.labels(queue=queue).set(size)

def track_queue_latency(queue: str, latency: float):
    """Track queue latency.
    
    Args:
        queue: Queue name
        latency: Latency in seconds
    """
    QUEUE_LATENCY.labels(queue=queue).observe(latency)

def track_job_duration(job_type: str, duration: float):
    """Track job duration.
    
    Args:
        job_type: Type of job
        duration: Duration in seconds
    """
    JOB_DURATION.labels(type=job_type).observe(duration)

def track_job_status(job_type: str, status: str):
    """Track job status.
    
    Args:
        job_type: Type of job
        status: Job status
    """
    JOB_STATUS.labels(
        type=job_type,
        status=status
    ).inc()

def get_resource_metrics() -> Dict[str, Any]:
    """Get current resource metrics.
    
    Returns:
        Dictionary of resource metrics
    """
    return {
        "memory": {
            label_dict["type"]: MEMORY_USAGE.labels(**label_dict)._value.get()
            for label_dict in MEMORY_USAGE._metrics
        },
        "cpu": {
            label_dict["type"]: CPU_USAGE.labels(**label_dict)._value.get()
            for label_dict in CPU_USAGE._metrics
        },
        "storage": {
            label_dict["type"]: STORAGE_USAGE.labels(**label_dict)._value.get()
            for label_dict in STORAGE_USAGE._metrics
        }
    }

def get_error_metrics() -> Dict[str, Any]:
    """Get current error metrics.
    
    Returns:
        Dictionary of error metrics
    """
    return {
        "counts": {
            label_dict["type"]: ERROR_COUNT.labels(**label_dict)._value.get()
            for label_dict in ERROR_COUNT._metrics
        },
        "severities": {
            f"{label_dict['type']}_{label_dict['severity']}": ERROR_SEVERITY.labels(**label_dict)._value.get()
            for label_dict in ERROR_SEVERITY._metrics
        },
        "retries": {
            label_dict["type"]: ERROR_RETRY_COUNT.labels(**label_dict)._value.get()
            for label_dict in ERROR_RETRY_COUNT._metrics
        }
    }

def get_operation_metrics() -> Dict[str, Any]:
    """Get current operation metrics.
    
    Returns:
        Dictionary of operation metrics
    """
    return {
        "durations": {
            label_dict["operation"]: OPERATION_DURATION.labels(**label_dict)._sum.get()
            for label_dict in OPERATION_DURATION._metrics
        },
        "failures": {
            label_dict["operation"]: OPERATION_FAILURES.labels(**label_dict)._value.get()
            for label_dict in OPERATION_FAILURES._metrics
        },
        "successes": {
            label_dict["operation"]: OPERATION_SUCCESS.labels(**label_dict)._value.get()
            for label_dict in OPERATION_SUCCESS._metrics
        }
    }

def get_queue_metrics() -> Dict[str, Any]:
    """Get current queue metrics.
    
    Returns:
        Dictionary of queue metrics
    """
    return {
        "sizes": {
            label_dict["queue"]: QUEUE_SIZE.labels(**label_dict)._value.get()
            for label_dict in QUEUE_SIZE._metrics
        },
        "latencies": {
            label_dict["queue"]: QUEUE_LATENCY.labels(**label_dict)._sum.get()
            for label_dict in QUEUE_LATENCY._metrics
        }
    }

def get_job_metrics() -> Dict[str, Any]:
    """Get current job metrics.
    
    Returns:
        Dictionary of job metrics
    """
    return {
        "durations": {
            label_dict["type"]: JOB_DURATION.labels(**label_dict)._sum.get()
            for label_dict in JOB_DURATION._metrics
        },
        "statuses": {
            f"{label_dict['type']}_{label_dict['status']}": JOB_STATUS.labels(**label_dict)._value.get()
            for label_dict in JOB_STATUS._metrics
        }
    }
