"""Metrics for transcriber service."""

from prometheus_client import Counter, Histogram, Gauge

# Transcription metrics
TRANSCRIPTION_DURATION = Histogram(
    "transcribo_transcription_duration_seconds",
    "Time spent on transcription",
    buckets=[30, 60, 120, 300, 600, 1200, 1800, 3600]  # 30s to 1h buckets
)

TRANSCRIPTION_ERRORS = Counter(
    "transcribo_transcription_errors_total",
    "Total number of transcription errors"
)

# Model metrics
MODEL_LOAD_TIME = Histogram(
    "transcribo_model_load_duration_seconds",
    "Time spent loading models",
    buckets=[1, 5, 10, 30, 60, 120]  # 1s to 2m buckets
)

MODEL_INFERENCE_TIME = Histogram(
    "transcribo_model_inference_duration_seconds",
    "Time spent on model inference",
    buckets=[1, 5, 10, 30, 60, 120]  # 1s to 2m buckets
)

# Resource metrics
MEMORY_USAGE = Gauge(
    "transcribo_memory_bytes",
    "Memory usage in bytes",
    ["type"]  # cuda or system
)

# Utility functions for tracking metrics
def track_transcription(duration: float):
    """Track transcription duration."""
    TRANSCRIPTION_DURATION.observe(duration)

def track_transcription_error():
    """Track transcription error."""
    TRANSCRIPTION_ERRORS.inc()

def track_model_load(duration: float):
    """Track model load time."""
    MODEL_LOAD_TIME.observe(duration)

def track_model_inference(duration: float):
    """Track model inference time."""
    MODEL_INFERENCE_TIME.observe(duration)

def track_memory_usage(bytes_used: int, memory_type: str = "system"):
    """Track memory usage."""
    MEMORY_USAGE.labels(type=memory_type).set(bytes_used)
