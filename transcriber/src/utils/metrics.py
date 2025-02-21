from prometheus_client import Counter, Histogram, Summary, Gauge
import functools
import time
import torch
import asyncio
from typing import Optional

# Transcription metrics
TRANSCRIPTION_DURATION = Histogram(
    'transcribo_transcription_duration_seconds',
    'Time spent on transcription',
    ['status'],
    buckets=[30, 60, 120, 300, 600, 1200, 1800]
)

TRANSCRIPTION_TOTAL = Counter(
    'transcribo_transcriptions_total',
    'Total number of transcriptions',
    ['status']  # success/failure
)

AUDIO_DURATION = Summary(
    'transcribo_audio_duration_seconds',
    'Duration of processed audio files'
)

WORD_COUNT = Counter(
    'transcribo_word_count_total',
    'Total number of transcribed words',
    ['language']
)

FOREIGN_SEGMENTS = Counter(
    'transcribo_foreign_segments_total',
    'Number of segments in foreign languages',
    ['language']
)

# Model metrics
MODEL_LOAD_TIME = Histogram(
    'transcribo_model_load_duration_seconds',
    'Time spent loading models',
    ['model'],  # whisper/diarization
    buckets=[1, 5, 10, 30, 60]
)

GPU_MEMORY_USAGE = Gauge(
    'transcribo_gpu_memory_bytes',
    'GPU memory usage in bytes',
    ['type']  # allocated/reserved
)

MODEL_INFERENCE_TIME = Histogram(
    'transcribo_model_inference_duration_seconds',
    'Time spent on model inference',
    ['operation'],  # transcribe/align/diarize
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0]
)

AUDIO_PROCESSING_TIME = Histogram(
    'transcribo_audio_processing_duration_seconds',
    'Time spent on audio processing',
    ['operation'],  # convert/merge/filter
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0]
)

def track_time(metric: Histogram, labels: Optional[dict] = None):
    """Decorator to track time spent in a function using a Histogram"""
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
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
                    metric.labels(**{**labels, "status": "error"}).observe(duration)
                else:
                    metric.labels(status="error").observe(duration)
                raise e
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                if labels:
                    metric.labels(**labels).observe(duration)
                else:
                    metric.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                if labels:
                    metric.labels(**{**labels, "status": "error"}).observe(duration)
                else:
                    metric.labels(status="error").observe(duration)
                raise e
                
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def track_gpu_memory():
    """Track GPU memory usage"""
    if torch.cuda.is_available():
        # Track allocated memory
        allocated = torch.cuda.memory_allocated()
        GPU_MEMORY_USAGE.labels(type="allocated").set(allocated)
        
        # Track reserved memory
        reserved = torch.cuda.memory_reserved()
        GPU_MEMORY_USAGE.labels(type="reserved").set(reserved)

def count_words(text: str, language: str):
    """Count words in text and update metrics"""
    words = len(text.split())
    WORD_COUNT.labels(language=language).inc(words)
    return words

def track_foreign_segment(language: str):
    """Track foreign language segment"""
    FOREIGN_SEGMENTS.labels(language=language).inc()

def track_audio_duration(duration: float):
    """Track audio duration"""
    AUDIO_DURATION.observe(duration)

def track_model_load_time(model_name: str, duration: float):
    """Track model loading time"""
    MODEL_LOAD_TIME.labels(model=model_name).observe(duration)

def track_inference_time(operation: str, duration: float):
    """Track model inference time"""
    MODEL_INFERENCE_TIME.labels(operation=operation).observe(duration)

def track_audio_processing(operation: str, duration: float):
    """Track audio processing time"""
    AUDIO_PROCESSING_TIME.labels(operation=operation).observe(duration)
