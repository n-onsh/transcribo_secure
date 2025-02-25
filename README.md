# Transcribo Secure

A secure audio transcription service with support for multiple languages.

## Features

- Multi-language support (German, English, French, Italian)
- End-to-end encryption
- Secure file handling
- Batch processing via ZIP files
- Real-time progress tracking
- Job management and monitoring

## Prerequisites

- Docker & Docker Compose
- NVIDIA CUDA Toolkit (for GPU support)

## Quick Start

1. Copy the environment template:
```bash
cp .env.example .env
```

2. Configure your environment variables in `.env`:
   - Set `HF_AUTH_TOKEN` (Get from https://huggingface.co/settings/tokens)
   - Set secure passwords for PostgreSQL and MinIO
   - Configure encryption settings (local key or Azure Key Vault)

3. Start the services:
```bash
docker-compose up -d
```

4. Access the application:
   - Frontend: https://app.localhost
   - API: https://api.localhost
   - MinIO Console: https://minio-console.localhost
   - Metrics: https://metrics.localhost

## Environment Variables

### Required Settings
- `HF_AUTH_TOKEN`: HuggingFace API token
- `ENCRYPTION_KEY`: Base64 encoded 32-byte key (if using local encryption)
- `POSTGRES_PASSWORD`: PostgreSQL password
- `MINIO_ROOT_PASSWORD`: MinIO root password
- `JWT_SECRET_KEY`: Secret for JWT token generation

### Optional Settings
- Azure Key Vault configuration (if not using local encryption)
- Email settings (for alerts)
- GPU settings (for hardware acceleration)

## Architecture

The system consists of several containerized services:

- Frontend: User interface and file upload
- Backend: API and job management
- Transcriber: Audio processing service
- PostgreSQL: Database
- MinIO: Object storage
- Traefik: Reverse proxy and SSL termination
- Monitoring stack (Grafana, Prometheus, Loki)

## Security

- End-to-end encryption for all files
- Secure key management
- Access control and authentication
- TLS for all communications
- Regular security updates

## Support

For issues and feature requests, please contact your system administrator.
