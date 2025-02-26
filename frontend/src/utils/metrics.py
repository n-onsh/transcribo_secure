"""Frontend metrics configuration and utilities."""

from prometheus_client import Counter, Histogram, Gauge
import asyncio
import time

# HTTP metrics
HTTP_REQUESTS_TOTAL = Counter(
    "transcribo_frontend_http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint"]
)

HTTP_REQUEST_DURATION = Histogram(
    "transcribo_frontend_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"]
)

FILE_UPLOAD_TOTAL = Counter(
    "transcribo_frontend_file_uploads_total",
    "Total number of file uploads",
    ["status"]
)

JOB_STATUS_TOTAL = Counter(
    "transcribo_frontend_job_status_total",
    "Total number of jobs by status",
    ["status"]
)

# Performance Metrics
TIME_TO_INTERACTIVE = Histogram(
    "transcribo_frontend_time_to_interactive_seconds",
    "Time until page becomes interactive",
    ["page"]
)

API_RESPONSE_TIME = Histogram(
    "transcribo_frontend_api_response_seconds",
    "API request duration",
    ["endpoint", "method"]
)

FRONTEND_RENDER_TIME = Histogram(
    "transcribo_frontend_render_duration_seconds",
    "Component render duration",
    ["component"]
)

# Task Metrics
TASK_COMPLETION = Counter(
    "transcribo_frontend_task_completion_total",
    "Number of completed tasks",
    ["type"]
)

TASK_ABANDONMENT = Counter(
    "transcribo_frontend_task_abandonment_total",
    "Number of abandoned tasks",
    ["type"]
)

TASK_DURATION = Histogram(
    "transcribo_frontend_task_duration_seconds",
    "Time spent on tasks",
    ["type"]
)

# Session Metrics
SESSION_DURATION = Histogram(
    "transcribo_frontend_session_duration_seconds",
    "User session duration"
)

SESSION_ACTIVITY = Counter(
    "transcribo_frontend_session_actions_total",
    "Number of user actions",
    ["action_type"]
)

CONCURRENT_USERS = Gauge(
    "transcribo_frontend_concurrent_users",
    "Number of active users"
)

# Navigation Metrics
PAGE_TRANSITIONS = Counter(
    "transcribo_frontend_page_transitions_total",
    "Number of page transitions",
    ["from_page", "to_page"]
)

FEATURE_USAGE = Counter(
    "transcribo_frontend_feature_usage_total",
    "Feature usage count",
    ["feature"]
)

# Error Metrics
UI_ERRORS = Counter(
    "transcribo_frontend_errors_total",
    "Number of UI errors",
    ["error_type"]
)

VALIDATION_FAILURES = Counter(
    "transcribo_frontend_validation_failures_total",
    "Number of validation failures",
    ["field"]
)

# Resource Metrics
CLIENT_MEMORY = Gauge(
    "transcribo_frontend_memory_bytes",
    "Frontend memory usage",
    ["type"]  # heap/total
)

CLIENT_CPU = Gauge(
    "transcribo_frontend_cpu_usage_percent",
    "Frontend CPU usage"
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
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                increment_counter(counter, error_labels)
                raise
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_labels = {**labels, "error": type(e).__name__} if labels else {"error": type(e).__name__}
                increment_counter(counter, error_labels)
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
