"""Metrics collection utilities."""

import time
import functools
from typing import Dict, Any, Optional, Callable, TypeVar, cast
from prometheus_client import Counter, Gauge, Histogram, Summary
from ..types import MetricLabels, MetricValue, MetricCallback

# Type variable for decorated functions
F = TypeVar('F', bound=Callable[..., Any])

# Service operation metrics
SERVICE_OPERATION_DURATION = Histogram(
    'service_operation_duration_seconds',
    'Duration of service operations',
    ['service', 'operation']
)

# Database metrics
DB_OPERATION_DURATION = Histogram(
    'db_operation_duration_seconds',
    'Duration of database operations',
    ['operation']
)
DB_OPERATIONS = Counter(
    'db_operations_total',
    'Number of database operations',
    ['operation']
)
DB_ERRORS = Counter(
    'db_errors_total',
    'Number of database errors'
)
DB_CONNECTIONS = Gauge(
    'db_connections',
    'Number of active database connections'
)
DB_POOL_SIZE = Gauge(
    'db_pool_size',
    'Database connection pool size',
    ['type']  # idle, used, total
)

# Job metrics
JOB_PROCESSING_TIME = Histogram(
    'job_processing_time_seconds',
    'Time taken to process jobs',
    ['type']  # audio, video, zip
)
JOB_STATUS_COUNT = Counter(
    'job_status_total',
    'Number of jobs by status',
    ['status']
)
JOB_ERROR_COUNT = Counter(
    'job_errors_total',
    'Number of job processing errors',
    ['type']
)

# ZIP processing metrics
ZIP_PROCESSING_TIME = Histogram(
    'zip_processing_time_seconds',
    'Time taken to process ZIP files'
)
ZIP_FILE_COUNT = Counter(
    'zip_files_total',
    'Number of files processed from ZIP archives'
)

# Key management metrics
KEY_OPERATIONS = Counter(
    'key_operations_total',
    'Number of key operations',
    ['operation']
)
KEY_ERRORS = Counter(
    'key_errors_total',
    'Number of key operation errors'
)
KEY_LATENCY = Histogram(
    'key_operation_latency_seconds',
    'Latency of key operations'
)

# Resource metrics
RESOURCE_USAGE = Gauge(
    'resource_usage',
    'Resource usage metrics',
    ['resource', 'type']  # cpu/memory/disk, used/total
)

def track_time(
    metric: Histogram,
    labels: Optional[Dict[str, str]] = None
) -> Callable[[F], F]:
    """Decorator to track operation timing.
    
    Args:
        metric: Prometheus histogram metric
        labels: Optional metric labels
        
    Returns:
        Decorated function that tracks timing
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
                raise
        return cast(F, wrapper)
    return decorator

def track_db_operation(operation: str) -> None:
    """Track database operation.
    
    Args:
        operation: Operation name
    """
    DB_OPERATIONS.labels(operation=operation).inc()

def track_db_error() -> None:
    """Track database error."""
    DB_ERRORS.inc()

def track_db_latency(duration: float) -> None:
    """Track database operation latency.
    
    Args:
        duration: Operation duration in seconds
    """
    DB_OPERATION_DURATION.observe(duration)

def track_db_connection(count: int) -> None:
    """Track database connection count.
    
    Args:
        count: Number of connections
    """
    DB_CONNECTIONS.set(count)

def track_job_processing(
    duration: float,
    job_type: str
) -> None:
    """Track job processing time.
    
    Args:
        duration: Processing duration in seconds
        job_type: Type of job
    """
    JOB_PROCESSING_TIME.labels(type=job_type).observe(duration)

def track_job_status(status: str) -> None:
    """Track job status.
    
    Args:
        status: Job status
    """
    JOB_STATUS_COUNT.labels(status=status).inc()

def track_job_error(error_type: str = "unknown") -> None:
    """Track job error.
    
    Args:
        error_type: Type of error
    """
    JOB_ERROR_COUNT.labels(type=error_type).inc()

def track_zip_processing(duration: float) -> None:
    """Track ZIP processing time.
    
    Args:
        duration: Processing duration in seconds
    """
    ZIP_PROCESSING_TIME.observe(duration)

def track_key_operation(operation: str) -> None:
    """Track key operation.
    
    Args:
        operation: Operation name
    """
    KEY_OPERATIONS.labels(operation=operation).inc()

def track_key_error() -> None:
    """Track key operation error."""
    KEY_ERRORS.inc()

def track_key_latency(duration: float) -> None:
    """Track key operation latency.
    
    Args:
        duration: Operation duration in seconds
    """
    KEY_LATENCY.observe(duration)

def track_resource_usage(
    resource: str,
    usage_type: str,
    value: float
) -> None:
    """Track resource usage.
    
    Args:
        resource: Resource name (cpu, memory, disk)
        usage_type: Usage type (used, total)
        value: Usage value
    """
    RESOURCE_USAGE.labels(
        resource=resource,
        type=usage_type
    ).set(value)

class MetricTracker:
    """Context manager for tracking operation metrics."""
    
    def __init__(
        self,
        metric: Histogram,
        labels: Optional[MetricLabels] = None,
        error_counter: Optional[Counter] = None
    ) -> None:
        """Initialize metric tracker.
        
        Args:
            metric: Prometheus histogram metric
            labels: Optional metric labels
            error_counter: Optional error counter metric
        """
        self.metric = metric
        self.labels = labels
        self.error_counter = error_counter
        self.start_time: float = 0.0
        
    async def __aenter__(self) -> 'MetricTracker':
        """Enter context manager."""
        self.start_time = time.time()
        return self
        
    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Optional[Any]
    ) -> None:
        """Exit context manager.
        
        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        duration = time.time() - self.start_time
        
        if self.labels:
            self.metric.labels(**self.labels).observe(duration)
        else:
            self.metric.observe(duration)
            
        if exc_type is not None and self.error_counter:
            self.error_counter.inc()

class ResourceMetrics:
    """Resource usage metrics collector."""
    
    def __init__(self) -> None:
        """Initialize resource metrics."""
        self.metrics: Dict[str, MetricCallback] = {}
        
    def register_metric(
        self,
        name: str,
        callback: MetricCallback
    ) -> None:
        """Register a metric callback.
        
        Args:
            name: Metric name
            callback: Callback function that returns metric value
        """
        self.metrics[name] = callback
        
    def collect(self) -> Dict[str, MetricValue]:
        """Collect all registered metrics.
        
        Returns:
            Dictionary of metric values
        """
        return {
            name: callback()
            for name, callback in self.metrics.items()
        }
        
    def track(self) -> None:
        """Track all registered metrics."""
        for name, value in self.collect().items():
            if isinstance(value, (int, float)):
                track_resource_usage(
                    resource=name.split('.')[0],
                    usage_type=name.split('.')[1],
                    value=float(value)
                )
