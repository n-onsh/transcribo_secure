from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import time
from .routes import files, jobs, transcriber
from .services.database import DatabaseService
from .services.storage import StorageService
from .middleware.auth import AzureADAuth
from .utils.logging import setup_logging, LogContext, get_logger
import uuid
from typing import Dict

# Setup logging
setup_logging(
    level="INFO",
    log_file="logs/backend-api.log",
    json_format=True
)

logger = logging.getLogger(__name__)

# Initialize auth
auth_handler = AzureADAuth()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application"""
    try:
        # Initialize services
        db = DatabaseService()
        storage = StorageService()
        
        # Initialize
        await db.initialize_database()
        await storage.init_buckets()
        logger.info("Backend services initialized")
        
        yield
        
        await db.close()
        logger.info("Backend services stopped")
        
    except Exception as e:
        logger.error(f"Startup/shutdown error: {str(e)}")
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
            # Process request without start log
            response = await call_next(request)
            
            # Calculate duration
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
            
        except Exception as e:
            # Log error more concisely
            logger.error(
                f"{request.method} {request.url.path} failed",
                exc_info=e,
                extra={"dur": f"{time.time() - start_time:.2f}s"}
            )
            raise

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get authenticated user
async def get_current_user(request: Request = None) -> Dict:
    """Get authenticated user from request state"""
    if not request or not hasattr(request.state, "user"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return request.state.user

# Include routers with auth
app.include_router(
    files.router,
    prefix="/api/v1",
    dependencies=[Depends(auth_handler), Depends(get_current_user)]
)
app.include_router(
    jobs.router,
    prefix="/api/v1",
    dependencies=[Depends(auth_handler), Depends(get_current_user)]
)
app.include_router(
    transcriber.router,
    prefix="/api/v1/transcriber",
    dependencies=[Depends(auth_handler), Depends(get_current_user)]
)

@app.get("/health")
async def health_check():
    """Basic health check endpoint - no auth required"""
    return {
        "status": "healthy",
        "timestamp": time.time()
    }

@app.get("/api/v1/me", dependencies=[Depends(auth_handler)])
async def get_user_info(user: Dict = Depends(get_current_user)):
    """Get authenticated user info"""
    return user
