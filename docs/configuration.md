# Configuration Guide

This document describes how to configure the Transcribo application using environment variables.

## Overview

The application uses a centralized configuration system that loads settings from environment variables. The configuration is validated at startup to ensure all required values are present and correctly formatted.

## Configuration Files

1. `.env` file in the project root directory
   - Contains environment-specific configuration
   - Not committed to version control
   - Use `.env.example` as a template

2. `.env.example`
   - Template file showing all available configuration options
   - Contains default values and documentation
   - Committed to version control

## Configuration Categories

### Database Configuration

```env
# Database connection settings
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=transcribo
POSTGRES_USER=transcribo_user
POSTGRES_PASSWORD=your_secure_password_here

# Connection pool settings
POSTGRES_POOL_SIZE=5
POSTGRES_MAX_OVERFLOW=10
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_RECYCLE=1800
```

### Authentication Configuration

```env
# Authentication mode (azure_ad or jwt)
AUTH_MODE=azure_ad

# Azure AD settings (required if AUTH_MODE=azure_ad)
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret

# JWT settings (required if AUTH_MODE=jwt)
JWT_SECRET_KEY=your_secure_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_MINUTES=1440
JWT_AUDIENCE=transcribo-api
JWT_ISSUER=transcribo-auth
```

### Storage Configuration

```env
# Storage provider settings
MINIO_HOST=minio
MINIO_PORT=9000
MINIO_ACCESS_KEY=your_access_key_here
MINIO_SECRET_KEY=your_secret_key_here
MINIO_BUCKET=transcribo
MINIO_SECURE=false
MINIO_REGION=us-east-1

# File handling settings
MAX_FILE_SIZE=104857600  # 100MB
ALLOWED_EXTENSIONS=.mp3,.wav,.m4a
STORAGE_PATH=/data
```

### Transcriber Configuration

```env
# Device settings
DEVICE=cuda
BATCH_SIZE=32
COMPUTE_TYPE=float16

# Language settings
DEFAULT_LANGUAGE=de
SUPPORTED_LANGUAGES=de,en,fr,it

# Scaling settings
WORKER_COUNT=1
TRANSCRIBER_REPLICAS=1
```

### Application Configuration

```env
# Environment settings
ENVIRONMENT=development  # development, testing, production
LOG_LEVEL=info  # debug, info, warning, error, critical
DEBUG=false

# Service settings
HOST=0.0.0.0
PORT=8000
WORKERS=1
```

## Usage in Code

### Accessing Configuration

The configuration is available through the `config` object exported by the `config` module:

```python
from src.config import config

# Access configuration values
database_host = config.database.host
auth_mode = config.auth.mode
storage_bucket = config.storage.bucket_name
```

### Configuration Models

The configuration is defined using Pydantic models, which provide type safety and validation:

```python
from src.config import (
    AppConfig,
    DatabaseConfig,
    AuthConfig,
    StorageConfig,
    TranscriberConfig
)

# Example: Create a database configuration
db_config = DatabaseConfig(
    host="localhost",
    port=5432,
    database="test",
    username="user",
    password="pass"
)

# Access the connection string
connection_string = db_config.connection_string
```

### Service Provider Integration

The configuration is integrated with the service provider for dependency injection:

```python
from src.services.provider import service_provider

# Get configuration from service provider
config = service_provider.get_config()

# Use configuration in services
class DatabaseService(BaseService):
    def __init__(self, settings):
        super().__init__(settings)
        self.config = service_provider.get_config()
        self.connection_string = self.config.database.connection_string
```

## Environment Variables

### Required Variables

These environment variables must be set:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- Authentication variables (depending on mode):
  - For Azure AD: `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`
  - For JWT: `JWT_SECRET_KEY`

### Optional Variables

All other variables have default values and are optional. See `.env.example` for the complete list of available variables and their default values.

## Validation

The configuration system validates all values at startup:

1. Environment variables are loaded
2. Values are converted to appropriate types
3. Configuration models validate the values
4. Required values are checked
5. Relationships between values are validated

If validation fails, the application will not start and will display detailed error messages.

## Best Practices

1. Always use the configuration system instead of accessing environment variables directly
2. Keep sensitive values in environment variables, not in code
3. Use the type-safe configuration models
4. Document any new configuration options in `.env.example`
5. Validate configuration values at startup
6. Use appropriate default values
7. Keep configuration organized by category
8. Use descriptive names for configuration options

## Adding New Configuration

To add new configuration options:

1. Add the option to the appropriate configuration model in `src/config/models.py`
2. Add validation if needed
3. Add the environment variable mapping in `src/config/service.py`
4. Update `.env.example` with the new option
5. Update this documentation
6. Add tests for the new configuration option
