# Transcriber Service

The Transcriber Service is responsible for processing audio files and generating transcriptions using WhisperX and speaker diarization.

## Features

- State-of-the-art transcription using WhisperX (Whisper v3 large model)
- Speaker diarization using pyannote.audio
- Support for multiple languages (de, en, fr, it)
- Custom vocabulary support
- Chunked processing for large files
- Prometheus metrics for monitoring
- Health and readiness checks

## Prerequisites

- Docker
- NVIDIA CUDA Toolkit (for GPU support)
- HuggingFace API Token (for model access)

## Environment Variables

### Required
- `HF_AUTH_TOKEN`: HuggingFace API token for model access

### Optional
- `DEVICE`: Device to use for inference (default: "cpu", options: "cpu", "cuda")
- `BATCH_SIZE`: Batch size for inference (default: 32)
- `BACKEND_API_URL`: URL of the backend API (default: "http://backend:8080/api/v1")
- `MODEL_PATH`: Path to store models (default: "/models")
- `CACHE_DIR`: Path for model cache (default: "/cache")
- `MAX_CONCURRENT_JOBS`: Maximum number of concurrent transcription jobs (default: 2)
- `CHUNK_SIZE`: Audio chunk size in seconds (default: 30)
- `MAX_RETRIES`: Maximum number of retries for failed operations (default: 3)
- `RETRY_DELAY`: Delay between retries in seconds (default: 1.0)
- `SUPPORTED_LANGUAGES`: Comma-separated list of supported languages (default: "de,en,fr,it")
- `DEFAULT_LANGUAGE`: Default language for transcription (default: "de")

## API Endpoints

### Health Check
```
GET /health
```
Returns service health status.

### Readiness Check
```
GET /ready
```
Returns service readiness status.

### Process Job
```
POST /jobs/{job_id}/process
```
Start processing a transcription job.

### Metrics
```
GET /metrics
```
Prometheus metrics endpoint.

## Metrics

The service exposes the following Prometheus metrics:

- `transcribo_transcription_duration_seconds`: Time spent on transcription
- `transcribo_transcription_errors_total`: Total number of transcription errors
- `transcribo_model_load_duration_seconds`: Time spent loading models
- `transcribo_model_inference_duration_seconds`: Time spent on model inference
- `transcribo_memory_bytes`: Memory usage in bytes

## Development

1. Install dependencies:
```bash
pip install -r requirements.base.txt
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
export HF_AUTH_TOKEN=your-token-here
```

3. Run the service:
```bash
python -m src.main
```

## Docker

Build the image:
```bash
docker build -t transcribo-transcriber --build-arg HF_AUTH_TOKEN=your-token-here .
```

Run the container:
```bash
docker run -p 8000:8000 \
  -e DEVICE=cpu \
  -e BATCH_SIZE=32 \
  -e BACKEND_API_URL=http://backend:8080/api/v1 \
  transcribo-transcriber
```

## License

This project is licensed under the MIT License.
