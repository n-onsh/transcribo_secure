# Setup Guide

## Prerequisites

- Docker and Docker Compose
- NVIDIA GPU with CUDA support (for transcription)
- FFmpeg
- Python 3.10+

## Environment Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd transcribo-secure
```

2. Create and configure environment variables:
```bash
cp .env.example .env
```

Required environment variables:
```ini
# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=transcribo
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_password

# Storage
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_ROOT_USER=your_minio_user
MINIO_ROOT_PASSWORD=your_minio_password

# Security
JWT_SECRET_KEY=your_jwt_secret
STORAGE_SECRET=your_storage_secret

# Azure KeyVault (optional)
AZURE_KEYVAULT_URL=your_keyvault_url
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret

# Transcriber
DEVICE=cuda
BATCH_SIZE=32
HF_AUTH_TOKEN=your_huggingface_token
CUDA_VISIBLE_DEVICES=0
```

3. Build and start services:
```bash
docker-compose up -d
```

4. Initialize database:
```bash
docker-compose exec postgres psql -U transcribo_user -d transcribo -f /docker-entrypoint-initdb.d/init.sql
```

## Development Setup

1. Install development dependencies:
```bash
pip install -r requirements.test.txt
```

2. Set up pre-commit hooks:
```bash
pre-commit install
```

3. Run tests:
```bash
pytest tests/
```

## Service Configuration

### Database
- PostgreSQL 15
- Extensions: uuid-ossp, hstore
- Connection pooling enabled
- Auto-update timestamps
- Job queue with FOR UPDATE SKIP LOCKED
- NOTIFY/LISTEN for real-time updates

### Storage (MinIO)
- Buckets:
  - audio: Audio file storage
  - transcription: Transcription results
  - vocabulary: Custom vocabulary files
  - temp: Temporary file storage
- Streaming upload support:
  - Chunk-by-chunk processing
  - Progress tracking
  - Memory-efficient handling
- Versioning enabled for all buckets except temp
- File size limits:
  - Audio: 500MB
  - Transcription: 10MB
  - Vocabulary: 1MB
  - Temp: 1GB
- Compression before encryption
- End-to-end encryption

### Security
- JWT authentication
- CORS configuration
- Content Security Policy
- File validation and sanitization
- End-to-end encryption
- Secure streaming uploads
- Azure KeyVault integration (optional)
  * Development fallback to environment variables
  * Automatic migration path to production

### Monitoring
- OpenTelemetry integration:
  * Structured logging with rich context
  * Distributed tracing
  * Metrics collection
  * Log correlation
- Grafana dashboards:
  * System health monitoring
  * Job processing metrics
  * Storage utilization
  * Error tracking
- Log aggregation in Loki:
  * Centralized logging
  * Log correlation with traces
  * Real-time log analysis
  * Structured log querying
- Prometheus metrics:
  * Performance monitoring
  * Resource utilization
  * Custom business metrics
  * Job queue metrics

## Troubleshooting

### Common Issues

1. Database Connection Errors
```
Check:
- Database credentials in .env
- Database service is running
- Network connectivity
- PostgreSQL logs for errors
```

2. Storage Access Issues
```
Check:
- MinIO credentials in .env
- MinIO service is running
- Bucket permissions
- Storage service logs
```

3. Transcription Failures
```
Check:
- GPU availability
- CUDA configuration
- HuggingFace token validity
- Transcriber service logs
```

### Logs

Access service logs through Grafana Loki:
1. Open Grafana (http://localhost:3000)
2. Go to Explore
3. Select Loki data source
4. Query logs by:
   - Service name
   - Log level
   - Custom attributes
   - Time range

Direct log access:
```bash
# Backend logs
docker-compose logs -f backend

# Transcriber logs
docker-compose logs -f transcriber

# Database logs
docker-compose logs -f postgres
```

### Monitoring

1. Access Grafana:
```
http://localhost:3000
Default credentials:
- Username: admin
- Password: admin
```

2. Available Dashboards:
- System Health: System metrics and resource usage
- Transcriber: Transcription job metrics and GPU usage
- Frontend: User experience and API metrics
- Storage: File operations and capacity metrics
- Logging: Log volume and error tracking

### Support

For additional support:
1. Check the troubleshooting guide
2. Review logs in Grafana Loki
3. Check Grafana dashboards
4. Contact system administrator
