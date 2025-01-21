from prometheus_client import Counter, Histogram, Summary, start_http_server
import functools
import time

# Transcription metrics
TRANSCRIPTION_DURATION = Histogram(
    'transcribo_transcription_duration_seconds',
    'Time spent on transcription',
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

# Model metrics
MODEL_LOAD_TIME = Histogram(
    'transcribo_model_load_duration_seconds',
    'Time spent loading models',
    buckets=[1, 5, 10, 30, 60]
)

GPU_MEMORY_USAGE = Summary(
    'transcribo_gpu_memory_bytes',
    'GPU memory usage in bytes'
)

def track_time(metric):
    """Decorator to track time spent in a function"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                metric.observe(duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                metric.observe(duration)
                raise e
        return wrapper
    return decorator

def init_metrics(port: int = 8000):
    """Initialize metrics server"""
    start_http_server(port)

def track_gpu_memory():
    """Track GPU memory usage if available"""
    try:
        import torch
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated()
            memory_reserved = torch.cuda.memory_reserved()
            GPU_MEMORY_USAGE.observe(memory_allocated)
    except Exception:
        pass