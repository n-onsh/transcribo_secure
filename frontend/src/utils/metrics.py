from opentelemetry import metrics

# Get meter
meter = metrics.get_meter_provider().get_meter("frontend")

# Create metrics
http_requests_total = meter.create_counter(
    "transcribo_frontend_http_requests_total",
    description="Total number of HTTP requests",
    unit="1"
)

http_request_duration = meter.create_histogram(
    "transcribo_frontend_http_request_duration_seconds",
    description="HTTP request duration",
    unit="s"
)

file_upload_total = meter.create_counter(
    "transcribo_frontend_file_uploads_total",
    description="Total number of file uploads",
    unit="1"
)

job_status_total = meter.create_counter(
    "transcribo_frontend_job_status_total",
    description="Total number of jobs by status",
    unit="1"
)

# Performance Metrics
time_to_interactive = meter.create_histogram(
    "transcribo_frontend_time_to_interactive_seconds",
    description="Time until page becomes interactive",
    unit="s"
)

api_response_time = meter.create_histogram(
    "transcribo_frontend_api_response_seconds",
    description="API request duration",
    unit="s"
)

frontend_render_time = meter.create_histogram(
    "transcribo_frontend_render_duration_seconds",
    description="Component render duration",
    unit="s"
)

# Task Metrics
task_completion = meter.create_counter(
    "transcribo_frontend_task_completion_total",
    description="Number of completed tasks",
    unit="1"
)

task_abandonment = meter.create_counter(
    "transcribo_frontend_task_abandonment_total",
    description="Number of abandoned tasks",
    unit="1"
)

task_duration = meter.create_histogram(
    "transcribo_frontend_task_duration_seconds",
    description="Time spent on tasks",
    unit="s"
)

# Session Metrics
session_duration = meter.create_histogram(
    "transcribo_frontend_session_duration_seconds",
    description="User session duration",
    unit="s"
)

session_activity = meter.create_counter(
    "transcribo_frontend_session_actions_total",
    description="Number of user actions",
    unit="1"
)

concurrent_users = meter.create_up_down_counter(
    "transcribo_frontend_concurrent_users",
    description="Number of active users",
    unit="1"
)

# Navigation Metrics
page_transitions = meter.create_counter(
    "transcribo_frontend_page_transitions_total",
    description="Number of page transitions",
    unit="1"
)

feature_usage = meter.create_counter(
    "transcribo_frontend_feature_usage_total",
    description="Feature usage count",
    unit="1"
)

# Error Metrics
ui_errors = meter.create_counter(
    "transcribo_frontend_errors_total",
    description="Number of UI errors",
    unit="1"
)

validation_failures = meter.create_counter(
    "transcribo_frontend_validation_failures_total",
    description="Number of validation failures",
    unit="1"
)

# Resource Metrics
client_memory = meter.create_up_down_counter(
    "transcribo_frontend_memory_bytes",
    description="Frontend memory usage",
    unit="By"
)

client_cpu = meter.create_up_down_counter(
    "transcribo_frontend_cpu_usage_percent",
    description="Frontend CPU usage",
    unit="1"
)

def setup_metrics():
    """Initialize metrics"""
    global http_requests_total, http_request_duration, file_upload_total, job_status_total
    
    # Re-create metrics to ensure they are initialized after OpenTelemetry setup
    http_requests_total = meter.create_counter(
        "transcribo_frontend_http_requests_total",
        description="Total number of HTTP requests",
        unit="1"
    )

    http_request_duration = meter.create_histogram(
        "transcribo_frontend_http_request_duration_seconds",
        description="HTTP request duration",
        unit="s"
    )

    file_upload_total = meter.create_counter(
        "transcribo_frontend_file_uploads_total",
        description="Total number of file uploads",
        unit="1"
    )

    job_status_total = meter.create_counter(
        "transcribo_frontend_job_status_total",
        description="Total number of jobs by status",
        unit="1"
    )

# Export metrics
__all__ = [
    'http_requests_total',
    'http_request_duration', 
    'file_upload_total',
    'job_status_total',
    'setup_metrics'
]
