from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
from .routes import files, jobs
from .services.database import DatabaseService
from .services.storage import StorageService
from .services.cleanup import CleanupService
from .routes import transcriber
from .middleware.file_validation import validate_file_middleware
from .config import get_settings
from .utils.logging import setup_logging, LogContext, get_logger
import uuid

# Setup logging
setup_logging(
    level="INFO",
    log_file="logs/backend-api.log",
    json_format=True
)

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application"""
    # Load settings
    settings = get_settings()
    logger.info("Starting backend-api")
    
    try:
        # Initialize services
        db = DatabaseService()
        storage = StorageService()
        cleanup = CleanupService(db, storage)
        
        # Initialize database and storage
        logger.info("Initializing database")
        await db.initialize_database()  # Changed from init_db to initialize_database
        
        logger.info("Initializing storage")
        await storage.init_buckets()
        
        # Start cleanup service
        logger.info("Starting cleanup service")
        await cleanup.start()
        
        yield
        
        # Cleanup on shutdown
        logger.info("Stopping cleanup service")
        await cleanup.stop()
        
        logger.info("Closing database connection")
        await db.close()
        
    except Exception as e:
        logger.error(f"Error during startup/shutdown: {str(e)}")
        raise

app = FastAPI(
    title="Transcribo Backend API",
    description="Secure API for audio/video transcription",
    version="1.0.0",
    lifespan=lifespan
)

# Add logging middleware
@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    # Generate request ID
    request_id = str(uuid.uuid4())
    
    # Start timer
    start_time = time.time()
    
    # Add context to all logs within this request
    with LogContext(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client_host=request.client.host if request.client else None
    ):
        try:
            # Log request
            logger.info(
                f"Request started: {request.method} {request.url.path}"
            )
            
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                f"Request completed: {request.method} {request.url.path}",
                extra={
                    "status_code": response.status_code,
                    "duration": duration
                }
            )
            
            return response
            
        except Exception as e:
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=e,
                extra={
                    "duration": time.time() - start_time
                }
            )
            raise

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add file validation middleware
app.middleware("http")(validate_file_middleware)

# Include routers
app.include_router(files.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(transcriber.router, prefix="/api/v1/transcriber")

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }