from opentelemetry import metrics
import functools
import time
import torch
import asyncio
from typing import Optional

# Get meter
meter = metrics.get_meter_provider().get_meter("transcriber")

# Processing Metrics
processing_duration = meter.create_histogram(
    "transcribo_transcriber_processing_duration_seconds",
    description="Time spent on processing",
    unit="s"
)

processing_total = meter.create_counter(
    "transcribo_transcriber_processing_total",
    description="Total number of processing tasks",
    unit="1"
)

processing_errors = meter.create_counter(
    "transcribo_transcriber_processing_errors_total",
    description="Total number of processing errors",
    unit="1"
)

# Model Performance Metrics
model_load_time = meter.create_histogram(
    "transcribo_transcriber_model_load_duration_seconds",
    description="Time spent loading models",
    unit="s"
)

model_inference_time = meter.create_histogram(
    "transcribo_transcriber_model_inference_duration_seconds",
    description="Time spent on model inference",
    unit="s"
)

# Resource Metrics
gpu_memory_usage = meter.create_up_down_counter(
    "transcribo_transcriber_gpu_memory_bytes",
    description="GPU memory usage in bytes",
    unit="By"
)

cpu_memory_usage = meter.create_up_down_counter(
    "transcribo_transcriber_cpu_memory_bytes",
    description="CPU memory usage in bytes",
    unit="By"
)

gpu_utilization = meter.create_up_down_counter(
    "transcribo_transcriber_gpu_utilization_percent",
    description="GPU utilization percentage",
    unit="1"
)

cpu_utilization = meter.create_up_down_counter(
    "transcribo_transcriber_cpu_utilization_percent",
    description="CPU utilization percentage",
    unit="1"
)

# Queue Metrics
queue_size = meter.create_up_down_counter(
    "transcribo_transcriber_queue_size",
    description="Number of tasks in queue",
    unit="1"
)

queue_wait_time = meter.create_histogram(
    "transcribo_transcriber_queue_wait_duration_seconds",
    description="Time spent in queue",
    unit="s"
)

def track_processing(duration: float, success: bool):
    """Track processing duration and result"""
    labels = {"status": "success" if success else "error"}
    processing_duration.record(duration, labels)
    processing_total.add(1, labels)
    if not success:
        processing_errors.add(1)

def track_model_load(model_type: str, duration: float):
    """Track model loading time"""
    model_load_time.record(duration, {"model_type": model_type})

def track_inference(operation_type: str, duration: float):
    """Track model inference time"""
    model_inference_time.record(duration, {"operation_type": operation_type})

def track_gpu_memory():
    """Track GPU memory usage"""
    if torch.cuda.is_available():
        # Track allocated memory
        allocated = torch.cuda.memory_allocated()
        gpu_memory_usage.add(allocated, {"type": "allocated"})
        
        # Track reserved memory
        reserved = torch.cuda.memory_reserved()
        gpu_memory_usage.add(reserved, {"type": "reserved"})

def track_resource_usage(cpu_memory: float, cpu_percent: float, gpu_percent: Optional[float] = None):
    """Track resource usage"""
    cpu_memory_usage.add(cpu_memory)
    cpu_utilization.add(cpu_percent)
    if gpu_percent is not None:
        gpu_utilization.add(gpu_percent)

def track_queue_metrics(size: int, wait_time: Optional[float] = None):
    """Track queue metrics"""
    queue_size.add(size)
    if wait_time is not None:
        queue_wait_time.record(wait_time)

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
