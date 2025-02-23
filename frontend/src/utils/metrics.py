from opentelemetry import metrics
from nicegui import app
import time
import functools
import psutil
from typing import Optional

# Initialize metrics as None
# Performance Metrics
time_to_interactive = None
api_response_time = None
frontend_render_time = None

# Task Metrics
task_completion = None
task_abandonment = None
task_duration = None

# Session Metrics
session_duration = None
session_activity = None
concurrent_users = None

# Navigation Metrics
page_transitions = None
feature_usage = None

# Error Metrics
ui_errors = None
validation_failures = None

# Resource Metrics
client_memory = None
client_cpu = None

def setup_metrics():
    """Set up metrics after meter provider is initialized"""
    global time_to_interactive, api_response_time, frontend_render_time, \
           task_completion, task_abandonment, task_duration, \
           session_duration, session_activity, concurrent_users, \
           page_transitions, feature_usage, ui_errors, validation_failures, \
           client_memory, client_cpu
    
    # Get meter
    meter = metrics.get_meter_provider().get_meter("frontend")

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

def track_page_interactive(page: str, duration: float):
    """Track time until page becomes interactive"""
    time_to_interactive.record(duration, {"page_type": page})

def track_api_call(endpoint_type: str, duration: float, success: bool):
    """Track API call duration and result"""
    api_response_time.record(duration, {
        "endpoint_type": endpoint_type,
        "status": "success" if success else "error"
    })

def track_render_time(component_type: str, duration: float):
    """Track component render duration"""
    frontend_render_time.record(duration, {"component_type": component_type})

def track_task_completion(task_type: str, success: bool):
    """Track task completion status"""
    if success:
        task_completion.add(1, {"task_type": task_type})
    else:
        task_abandonment.add(1, {"task_type": task_type})

def track_task_time(task_type: str, duration: float):
    """Track time spent on task"""
    task_duration.record(duration, {"task_type": task_type})

def track_session_time(duration: float):
    """Track session duration"""
    session_duration.record(duration)

def track_user_action(action_type: str):
    """Track user action"""
    session_activity.add(1, {"action_type": action_type})

def track_session_start():
    """Track new user session"""
    concurrent_users.add(1)

def track_session_end():
    """Track session end"""
    concurrent_users.add(-1)

def track_navigation(from_type: str, to_type: str):
    """Track page navigation"""
    page_transitions.add(1, {
        "from_type": from_type,
        "to_type": to_type
    })

def track_feature_use(feature_type: str):
    """Track feature usage"""
    feature_usage.add(1, {"feature_type": feature_type})

def track_ui_error(error_type: str):
    """Track UI error"""
    ui_errors.add(1, {"error_type": error_type})

def track_validation_failure(field_type: str):
    """Track validation failure"""
    validation_failures.add(1, {"field_type": field_type})

def track_resources():
    """Track client resource usage"""
    process = psutil.Process()
    memory = process.memory_info().rss
    cpu = process.cpu_percent()
    
    client_memory.add(memory)
    client_cpu.add(cpu)

def track_time(metric, labels: Optional[dict] = None):
    """Decorator to track time spent in a function"""
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
