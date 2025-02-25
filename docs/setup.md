# Setup Guide

## Prerequisites

- Python 3.9+
- Docker & Docker Compose
- NVIDIA CUDA Toolkit
- PostgreSQL client
- Azure CLI

## Environment Variables

### Core Configuration
```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=transcribo
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# Storage
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=your_password
MINIO_ENDPOINT=localhost:9000
MINIO_BUCKET=transcribo

# Azure AD
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_secret
```

### Language Configuration
```bash
# Supported languages
SUPPORTED_LANGUAGES=de,en,fr,it
DEFAULT_LANGUAGE=de

# Model paths
MODEL_BASE_PATH=/path/to/models
DIARIZATION_MODEL_PATH=/path/to/diarization
```

### Performance Configuration
```bash
# Time estimation
MAX_STATISTICS_SAMPLES=100
STATISTICS_WINDOW_DAYS=30
DEFAULT_PROCESSING_RATIO=2.0
MAX_CONFIDENCE_LEVEL=0.9

# Model caching
MODEL_CACHE_SIZE=5
CACHE_CLEANUP_INTERVAL=3600

# Resource limits
BATCH_SIZE=32
MAX_UPLOAD_SIZE=12GB
MAX_CONCURRENT_JOBS=4
```

### Scaling Configuration
```bash
# Service replicas
TRANSCRIBER_REPLICAS=3
WORKER_COUNT=2

# Resource limits
TRANSCRIBER_CPU_LIMIT=4
TRANSCRIBER_MEMORY_LIMIT=16G
GPU_MEMORY_LIMIT=8G
```

## Installation

1. Clone repository:
```bash
git clone https://github.com/your-org/transcribo-secure.git
cd transcribo-secure
```

2. Copy environment template:
```bash
cp .env.example .env
```

3. Configure environment variables in .env

4. Initialize database:
```bash
# Apply migrations
docker-compose run --rm backend alembic upgrade head

# Initialize statistics table
docker-compose run --rm backend python -m scripts.init_stats
```

5. Start services:
```bash
docker-compose up --build
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
pytest
```

## Production Deployment

1. Configure production environment:
```bash
# Set production variables
export ENVIRONMENT=production
export LOG_LEVEL=info
```

2. Deploy with Docker Compose:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

3. Initialize production database:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm backend alembic upgrade head
```

## Monitoring Setup

1. Access Grafana:
- URL: http://localhost:3000
- Default credentials: admin/admin

2. Import dashboards:
- System Health
- Transcriber Performance
- Job Statistics
- Time Estimation

3. Configure alerts:
- Processing time anomalies
- Resource utilization
- Error rates
- Cache performance

## Maintenance

### Database Maintenance

1. Clean old statistics:
```sql
-- Run periodically (e.g., via cron)
SELECT cleanup_old_statistics();
```

2. Optimize indexes:
```sql
-- Analyze tables
ANALYZE job_time_statistics;
ANALYZE jobs;

-- Reindex if needed
REINDEX TABLE job_time_statistics;
```

### Cache Maintenance

1. Monitor cache size:
```bash
# Check current cache usage
docker-compose exec transcriber python -m scripts.check_cache
```

2. Clear cache if needed:
```bash
# Clear model cache
docker-compose exec transcriber python -m scripts.clear_cache
```

### Performance Monitoring

1. Check processing metrics:
```bash
# Get performance stats
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance
```

2. Monitor resource usage:
```bash
# Check container stats
docker stats transcriber_1 transcriber_2 transcriber_3
```

## Troubleshooting

### Common Issues

1. Time Estimation Issues
- Check historical data availability
- Verify language support
- Monitor cache performance
- Check resource utilization

2. Performance Issues
- Monitor cache hit rates
- Check database query performance
- Verify resource allocation
- Monitor network latency

3. Resource Issues
- Check memory usage
- Monitor GPU utilization
- Verify disk space
- Check network bandwidth

### Debug Tools

1. Check job statistics:
```bash
# Get recent job stats
docker-compose exec backend python -m scripts.job_stats
```

2. Verify model cache:
```bash
# Check cache status
docker-compose exec transcriber python -m scripts.cache_status
```

3. Monitor performance:
```bash
# Get performance metrics
docker-compose exec backend python -m scripts.performance
```

## Security Notes

1. Authentication:
- Configure Azure AD properly
- Rotate secrets regularly
- Monitor token usage
- Check access logs

2. Data Protection:
- Enable encryption
- Secure key management
- Regular backups
- Access control

3. Network Security:
- Configure firewalls
- Use TLS
- Monitor traffic
- Rate limiting

## Upgrade Process

1. Backup data:
```bash
# Backup database
docker-compose exec db pg_dump -U postgres transcribo > backup.sql

# Backup statistics
docker-compose exec db pg_dump -U postgres -t job_time_statistics \
  transcribo > stats_backup.sql
```

2. Update services:
```bash
# Pull latest images
docker-compose pull

# Apply migrations
docker-compose run --rm backend alembic upgrade head

# Restart services
docker-compose up -d
```

3. Verify upgrade:
```bash
# Check service health
docker-compose ps

# Verify statistics
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/performance
