"""Backend application."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from .routes import auth, editor, files, jobs, keys, transcriber, viewer, vocabulary, verify, tags, offline, zip
from .middleware import auth as auth_middleware
from .middleware import error_handler, file_validation, metrics, security
from .services.provider import ServiceProvider
from .utils import setup_metrics
from .utils.logging import setup_logging

# Configure logging
setup_logging()

# Create FastAPI app
app = FastAPI()

# Create metrics app
metrics_app = make_asgi_app()

# Set up metrics
setup_metrics()

# Initialize service provider
service_provider = ServiceProvider()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(auth_middleware.AuthMiddleware)
app.add_middleware(error_handler.ErrorHandlerMiddleware)
app.add_middleware(file_validation.FileValidationMiddleware)
app.add_middleware(metrics.MetricsMiddleware)
app.add_middleware(security.SecurityMiddleware)

# Mount metrics endpoint
app.mount("/metrics", metrics_app)

# Include routers
app.include_router(auth.router)
app.include_router(editor.router)
app.include_router(files.router)
app.include_router(jobs.router)
app.include_router(keys.router)
app.include_router(transcriber.router)
app.include_router(viewer.router)
app.include_router(vocabulary.router)
app.include_router(verify.router)
app.include_router(tags.router)
app.include_router(offline.router)
app.include_router(zip.router)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.on_event("startup")
async def startup():
    """Initialize services on startup."""
    await service_provider.initialize()

@app.on_event("shutdown")
async def shutdown():
    """Clean up services on shutdown."""
    await service_provider.cleanup()
