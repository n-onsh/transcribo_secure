from fastapi import FastAPI, Request, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import asyncio
import time
import psutil
import uuid
import os
import logging
from typing import Dict, List
from prometheus_client import make_asgi_app, Gauge
from .routes import files, jobs, transcriber, auth, keys
from .services.database import DatabaseService
from .services.storage import StorageService
from .services.encryption import EncryptionService
from .services.job_manager import JobManager
from .middleware.auth import AuthMiddleware
from .middleware.error_handler import error_handler_middleware
from .middleware.metrics import MetricsMiddleware
from .middleware.security import SecurityHeadersMiddleware, SecurityConfig
from .middleware.rate_limiter import RateLimiter
from .utils.logging import setup_logging, LogContext, get_logger
from .utils.exceptions import AuthenticationError, ServiceUnavailableError
from .utils.metrics import (
    DB_CONNECTIONS,
    STORAGE_BYTES,
    update_gauge,
    increment_counter
)

import uuid
import os
import logging
from typing import Dict, List

# System metrics
SYSTEM_CPU_USAGE = Gauge(
    'transcribo_system_cpu_usage_percent',
    'System CPU usage percentage'
)
SYSTEM_DISK_USAGE = Gauge(
    'transcribo_system_disk_usage_bytes',
    'System disk usage in bytes',
    ['type']  # used/total
)

# Setup logging - using OTEL for centralized logging
setup_logging(
    level="WARNING",  # Reduce verbosity
    json_format=True
)

logger = logging.getLogger(__name__)

# Global auth handler
auth_handler = None

SYSTEM_MEMORY_USAGE = Gauge(
    'transcribo_system_memory_usage_bytes',
    'System memory usage in bytes',
    ['type']  # used/total
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application"""
    try:
        logger.warning("Starting service initialization...")  # Only critical startup messages
        
        # Initialize services
        try:
            global auth_handler
            auth_handler = AuthMiddleware()
            logger.warning("Auth handler initialized")  # Only critical startup messages
        except Exception as auth_error:
            logger.error(f"Auth handler initialization failed: {str(auth_error)}")
            raise
        
        try:
            db = DatabaseService()
            logger.warning("Database service instance created")  # Only critical startup messages
        except Exception as db_error:
            logger.error(f"Database service creation failed: {str(db_error)}")
            raise
        
        try:
            storage = StorageService(database_service=db)
            logger.warning("Storage service instance created")  # Only critical startup messages
        except Exception as storage_error:
            logger.error(f"Storage service creation failed: {str(storage_error)}")
            raise

        try:
            encryption = EncryptionService()
            logger.warning("Encryption service instance created")  # Only critical startup messages
        except Exception as e:
            logger.error(f"Failed to create encryption service: {str(e)}")
            raise

        try:
            job_manager = JobManager(storage=storage, db=db)
            await job_manager.start()
            logger.warning("Job manager initialized and started")  # Only critical startup messages
        except Exception as e:
            logger.error(f"Failed to initialize job manager: {str(e)}")
            raise

        # Initialize database and storage
        logger.info("Initializing database...")
        try:
            await db.initialize_database()
            logger.warning("Database initialized successfully")  # Only critical startup messages
        except Exception as db_init_error:
            logger.error(f"Database initialization failed: {str(db_init_error)}")
            raise
        
        logger.info("Initializing storage buckets...")
        try:
            await storage._init_buckets()
            logger.warning("Storage buckets initialized successfully")  # Only critical startup messages
        except Exception as storage_init_error:
            logger.error(f"Storage bucket initialization failed: {str(storage_init_error)}")
            raise

        try:
            # Initialize metrics
            update_gauge(DB_CONNECTIONS, await db.get_active_connections())

            # Get storage usage for each bucket
            buckets = ["audio", "transcription"]
            for bucket in buckets:
                bucket_size = await storage.get_bucket_size(bucket)
                update_gauge(STORAGE_BYTES, bucket_size, {"bucket": bucket})
        except Exception as metrics_error:
            logger.error(f"Metrics initialization failed: {str(metrics_error)}")
            raise

        logger.warning("Backend services initialized")  # Only critical startup messages

        # Start background tasks
        try:
            metrics_update_task = asyncio.create_task(update_metrics_periodically(db, storage))
            system_metrics_task = asyncio.create_task(update_system_metrics_periodically())
        except Exception as task_error:
            logger.error(f"Failed to create background tasks: {str(task_error)}")
            raise

        yield

        # Cancel background tasks
        metrics_update_task.cancel()
        system_metrics_task.cancel()
        try:
            await metrics_update_task
            await system_metrics_task
        except asyncio.CancelledError:
            pass
        except Exception as cancel_error:
            logger.error(f"Error cancelling background tasks: {str(cancel_error)}")

        if 'job_manager' in locals():
            await job_manager.stop()
        await db.close()
        logger.warning("Backend services stopped")  # Only critical startup messages

    except Exception as e:
        logger.error(f"Startup/shutdown error: {str(e)}")
        raise

async def update_metrics_periodically(db: DatabaseService, storage: StorageService):
    """Update metrics periodically"""
    while True:
        try:
            # Update DB metrics
            update_gauge(DB_CONNECTIONS, await db.get_active_connections())

            # Update storage metrics
            for bucket in ["audio", "transcription"]:
                bucket_size = await storage.get_bucket_size(bucket)
                update_gauge(STORAGE_BYTES, bucket_size, {"bucket": bucket})

            await asyncio.sleep(60)  # Update every minute

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error updating metrics: {str(e)}")
            await asyncio.sleep(10)  # Back off on error

async def update_system_metrics_periodically():
    """Update system metrics periodically"""
    while True:
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            SYSTEM_CPU_USAGE.set(cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            SYSTEM_MEMORY_USAGE.labels(type="used").set(memory.used)
            SYSTEM_MEMORY_USAGE.labels(type="total").set(memory.total)

            # Disk usage
            disk = psutil.disk_usage("/")
            SYSTEM_DISK_USAGE.labels(type="used").set(disk.used)
            SYSTEM_DISK_USAGE.labels(type="total").set(disk.total)

            await asyncio.sleep(15)  # Update every 15 seconds

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error updating system metrics: {str(e)}")
            await asyncio.sleep(5)  # Back off on error

async def check_service_health() -> Dict[str, Dict]:
    """Check health of all services"""
    services = {}

    # Check database
    try:
        db = DatabaseService()
        await db.get_active_connections()
        services["database"] = {
            "status": "healthy",
            "connections": len(db.pool._holders) if db.pool else 0
        }
    except Exception as e:
        services["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check storage
    try:
        storage = StorageService()
        services["storage"] = {
            "status": "healthy",
            "buckets": ["audio", "transcription"]
        }
    except Exception as e:
        services["storage"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check encryption
    try:
        from .services.encryption import EncryptionService
        encryption = EncryptionService()
        services["encryption"] = {
            "status": "healthy"
        }
    except Exception as e:
        services["encryption"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check job manager
    try:
        job_manager = JobManager()
        services["job_manager"] = {
            "status": "healthy",
            "active_jobs": len(job_manager.active_jobs),
            "max_concurrent_jobs": job_manager.max_concurrent_jobs
        }
    except Exception as e:
        services["job_manager"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check system resources
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        services["system"] = {
            "status": "healthy",
            "cpu_usage": cpu_percent,
            "memory_usage": {
                "used": memory.used,
                "total": memory.total,
                "percent": memory.percent
            },
            "disk_usage": {
                "used": disk.used,
                "total": disk.total,
                "percent": disk.percent
            }
        }
    except Exception as e:
        services["system"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    return services

def custom_openapi():
    """Customize OpenAPI schema"""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Transcribo Backend API",
        version="1.0.0",
        description="""
        Secure API for audio/video transcription with the following features:

        - **Authentication**: JWT-based authentication for secure access
        - **File Management**: Upload and manage audio/video files
        - **Transcription**: Automated transcription with speaker diarization
        - **Editing**: Edit and refine transcription results
        - **Vocabulary**: Custom vocabulary management for better accuracy

        For detailed documentation on each endpoint, see the descriptions below.
        """,
        routes=app.routes
    )

    # Add security scheme
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Enter your JWT token"
        }
    }

    # Add global security requirement
    openapi_schema["security"] = [{"bearerAuth": []}]

    # Add response examples
    openapi_schema["components"]["examples"] = {
        "ValidationError": {
            "summary": "Validation Error",
            "value": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid input data",
                "details": {
                    "field": "file_name",
                    "reason": "File name too long"
                }
            }
        },
        "AuthenticationError": {
            "summary": "Authentication Error",
            "value": {
                "code": "AUTHENTICATION_ERROR",
                "message": "Invalid or expired token"
            }
        },
        "ResourceNotFound": {
            "summary": "Resource Not Found",
            "value": {
                "code": "RESOURCE_NOT_FOUND",
                "message": "Job not found: 123e4567-e89b-12d3-a456-426614174000",
                "details": {
                    "resource_type": "job",
                    "resource_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            }
        }
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app = FastAPI(
        title="Transcribo Backend API",
        description="Secure API for audio/video transcription",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )
# Customize OpenAPI schema
app.openapi = custom_openapi

# Add middlewares in correct order (order matters!)
app.add_middleware(RateLimiter)  # Add rate limiting first
app.add_middleware(MetricsMiddleware)  # Then metrics
app.add_middleware(SecurityHeadersMiddleware)  # Then security headers
app.middleware("http")(error_handler_middleware)  # Finally error handler

# Create metrics app
metrics_app = make_asgi_app()

# Add logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Add request logging with timing and context"""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    with LogContext(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else None
    ):
        response = await call_next(request)

        duration = time.time() - start_time

        # Only log non-200 responses or slow requests
        if response.status_code != 200 or duration > 1.0:
            logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "status": response.status_code,
                    "dur": f"{duration:.2f}s"
                }
            )

        return response

# Configure CORS with security settings
app.add_middleware(
    CORSMiddleware,
    **SecurityConfig.get_cors_config()
)

# Mount metrics endpoint
app.mount("/metrics", metrics_app)

# Dependency to get authenticated user
async def get_current_user(request: Request = None) -> Dict:
    """Get authenticated user from request state

    Returns:
        Dict: User information including ID and roles

    Raises:
        AuthenticationError: If user is not authenticated
    """
    if not request or not hasattr(request.state, "user"):
        raise AuthenticationError("Not authenticated")
    return request.state.user

# Create auth dependency
async def auth_dependency(request: Request):
    if auth_handler is None:
        raise ServiceUnavailableError("auth", "Auth service not initialized")
    return await auth_handler(request, lambda r: r)

# Include auth router without auth dependency
app.include_router(
    auth.router,
    prefix="/api/v1"
)

# Include other routers with auth
app.include_router(
    files.router,
    prefix="/api/v1",
    dependencies=[Depends(auth_dependency), Depends(get_current_user)]
)

app.include_router(
    jobs.router,
    prefix="/api/v1",
    dependencies=[Depends(auth_dependency), Depends(get_current_user)]
)

app.include_router(
    transcriber.router,
    prefix="/api/v1/transcriber",
    dependencies=[Depends(auth_dependency), Depends(get_current_user)]
)

app.include_router(
    keys.router,
    prefix="/api/v1",
    dependencies=[Depends(auth_dependency), Depends(get_current_user)]
)

@app.get(
    "/api/v1/health",
    summary="Health Check",
    description="Detailed health check of all services",
    response_description="Health status of all services",
    responses={
        200: {
            "description": "All services are healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": 1645430400.0,
                        "version": "1.0.0",
                        "services": {
                            "database": {
                                "status": "healthy",
                                "connections": 5
                            },
                            "storage": {
                                "status": "healthy",
                                "buckets": ["audio", "transcription"]
                            },
                            "job_manager": {
                                "status": "healthy",
                                "active_jobs": 0,
                                "max_concurrent_jobs": 4
                            },
                            "system": {
                                "status": "healthy",
                                "cpu_usage": 25.5,
                                "memory_usage": {
                                    "used": 4294967296,
                                    "total": 8589934592,
                                    "percent": 50.0
                                },
                                "disk_usage": {
                                    "used": 107374182400,
                                    "total": 214748364800,
                                    "percent": 50.0
                                }
                            }
                        }
                    }
                }
            }
        },
        503: {
            "description": "One or more services are unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": 1645430400.0,
                        "version": "1.0.0",
                        "services": {
                            "database": {
                                "status": "unhealthy",
                                "error": "Connection failed"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def health_check():
    """Enhanced health check endpoint"""
    services = await check_service_health()

    # Check if any service is unhealthy
    status = "healthy"
    for service in services.values():
        if service["status"] == "unhealthy":
            status = "unhealthy"
            break

    response = {
        "status": status,
        "timestamp": time.time(),
        "version": "1.0.0",
        "services": services
    }

    if status == "unhealthy":
        return JSONResponse(
            status_code=503,
            content=response
        )

    return response

@app.get(
    "/api/v1/me",
    dependencies=[Depends(auth_dependency)],
    summary="Get User Info",
    description="Get information about the currently authenticated user",
    response_description="User information including ID and roles",
    responses={
        200: {
            "description": "User information retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "user123",
                        "roles": ["user"],
                        "name": "John Doe"
                    }
                }
            }
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {
                        "code": "AUTHENTICATION_ERROR",
                        "message": "Not authenticated"
                    }
                }
            }
        }
    }
)
async def get_user_info(user: Dict = Depends(get_current_user)):
    """Get authenticated user info"""
    return user

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
