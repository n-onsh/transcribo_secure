"""Utilities package for transcriber."""

from prometheus_client import start_http_server

from .logging import log_info, log_error, log_warning, log_debug
from .metrics import (
    track_transcription,
    track_transcription_error,
    track_model_load,
    track_model_inference,
    track_memory_usage,
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    MODEL_LOAD_TIME,
    MODEL_INFERENCE_TIME,
    MEMORY_USAGE
)

def setup_metrics(port: int = 8000):
    """Start Prometheus metrics server."""
    try:
        start_http_server(port)
        log_info(f"Metrics server started on port {port}")
    except Exception as e:
        log_error(f"Failed to start metrics server: {str(e)}")
        raise

__all__ = [
    'log_info',
    'log_error',
    'log_warning',
    'log_debug',
    'track_transcription',
    'track_transcription_error',
    'track_model_load',
    'track_model_inference',
    'track_memory_usage',
    'TRANSCRIPTION_DURATION',
    'TRANSCRIPTION_ERRORS',
    'MODEL_LOAD_TIME',
    'MODEL_INFERENCE_TIME',
    'MEMORY_USAGE',
    'setup_metrics'
]
