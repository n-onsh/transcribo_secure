"""Transcriber metrics configuration and utilities."""

from prometheus_client import Counter, Histogram, Gauge
import functools
import time
import torch
import asyncio
from typing import Optional

# Processing Metrics
PROCESSING_DURATION = Histogram(
    "transcribo_transcriber_processing_duration_seconds",
    "Time spent on processing",
    ["status"]
)

PROCESSING_TOTAL = Counter(
    "transcribo_transcriber_processing_total",
    "Total number of processing tasks",
    ["status"]
)

PROCESSING_ERRORS = Counter(
    "transcribo_transcriber_processing_errors_total",
    "Total number of processing errors"
)

# Model Performance Metrics
MODEL_LOAD_TIME = Histogram(
    "transcribo_transcriber_model_load_duration_seconds",
    "Time spent loading models",
    ["model_type"]
)

MODEL_INFERENCE_TIME = Histogram(
    "transcribo_transcriber_model_inference_duration_seconds",
    "Time spent on model inference",
    ["operation_type"]
)

# Resource Metrics
GPU_MEMORY_USAGE = Gauge(
    "transcribo_transcriber_gpu_memory_bytes",
    "GPU memory usage in bytes",
    ["type"]  # allocated/reserved
)

CPU_MEMORY_USAGE = Gauge(
    "transcribo_transcriber_cpu_memory_bytes",
    "CPU memory usage in bytes"
)

GPU_UTILIZATION = Gauge(
    "transcribo_transcriber_gpu_utilization_percent",
    "GPU utilization percentage"
)

CPU_UTILIZATION = Gauge(
    "transcribo_transcriber_cpu_utilization_percent",
    "CPU utilization percentage"
)

# Queue Metrics
QUEUE_SIZE = Gauge(
    "transcribo_transcriber_queue_size",
    "Number of tasks in queue"
)

QUEUE_WAIT_TIME = Histogram(
    "transcribo_transcriber_queue_wait_duration_seconds",
    "Time spent in queue"
)

def track_processing(duration: float, success: bool):
    """Track processing duration and result"""
    status = "success" if success else "error"
    PROCESSING_DURATION.labels(status=status).observe(duration)
    PROCESSING_TOTAL.labels(status=status).inc()
    if not success:
        PROCESSING_ERRORS.inc()

def track_model_load(model_type: str, duration: float):
    """Track model loading time"""
    MODEL_LOAD_TIME.labels(model_type=model_type).observe(duration)

def track_inference(operation_type: str, duration: float):
    """Track model inference time"""
    MODEL_INFERENCE_TIME.labels(operation_type=operation_type).observe(duration)

def track_gpu_memory():
    """Track GPU memory usage"""
    if torch.cuda.is_available():
        # Track allocated memory
        allocated = torch.cuda.memory_allocated()
        GPU_MEMORY_USAGE.labels(type="allocated").set(allocated)
        
        # Track reserved memory
        reserved = torch.cuda.memory_reserved()
        GPU_MEMORY_USAGE.labels(type="reserved").set(reserved)

def track_resource_usage(cpu_memory: float, cpu_percent: float, gpu_percent: Optional[float] = None):
    """Track resource usage"""
    CPU_MEMORY_USAGE.set(cpu_memory)
    CPU_UTILIZATION.set(cpu_percent)
    if gpu_percent is not None:
        GPU_UTILIZATION.set(gpu_percent)

def track_queue_metrics(size: int, wait_time: Optional[float] = None):
    """Track queue metrics"""
    QUEUE_SIZE.set(size)
    if wait_time is not None:
        QUEUE_WAIT_TIME.observe(wait_time)

def track_time(histogram: Histogram, labels: dict = None):
    """Decorator to track time spent in a function"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_labels = {**labels, "status": "error"} if labels else {"status": "error"}
                histogram.labels(**error_labels).observe(duration)
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                if labels:
                    histogram.labels(**labels).observe(duration)
                else:
                    histogram.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                error_labels = {**labels, "status": "error"} if labels else {"status": "error"}
                histogram.labels(**error_labels).observe(duration)
                raise
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator
