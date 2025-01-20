from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .routes import files
from .services.database import DatabaseService
from .services.storage import StorageService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize services
    db = DatabaseService()
    storage = StorageService()
    
    # Create database tables
    await db.init_db()
    # Create MinIO buckets
    await storage.init_buckets()
    
    yield
    
app = FastAPI(
    title="Transcribo Storage API",
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

# Include routers
app.include_router(files.router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}