from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .routes import files
from .services.database import DatabaseService
from .services.storage import StorageService
from .middleware.file_validation import validate_file_middleware
from .config import get_settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI application"""
    # Load settings
    settings = get_settings()
    
    # Initialize services
    db = DatabaseService()
    storage = StorageService()
    
    # Create database tables
    await db.init_db()
    # Create MinIO buckets
    await storage.init_buckets()
    
    yield
    
    # Cleanup
    await db.close()

app = FastAPI(
    title="Transcribo Storage API",
    description="Secure storage API for audio/video transcription",
    version="1.0.0",
    lifespan=lifespan
)

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

@app.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "database": True,  # We could add real checks here
            "storage": True,
            "encryption": True
        }
    }