"""Main FastAPI application."""

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import config
from .constants import API_V1_PREFIX, REQUEST_ID_HEADER
from .middleware.error_handler import setup_error_handling
from .middleware.request_id import RequestIDMiddleware
from .models.api import ApiResponse
from .routes import (
    auth,
    editor,
    files,
    jobs,
    keys,
    tags,
    transcriber,
    verify,
    viewer,
    vocabulary,
    zip
)
from .utils.logging import setup_logging
from .utils.metrics import setup_metrics

# Create FastAPI application
app = FastAPI(
    title="Transcribo",
    description="Secure transcription service",
    version="1.0.0",
    docs_url=f"{API_V1_PREFIX}/docs",
    redoc_url=f"{API_V1_PREFIX}/redoc",
    openapi_url=f"{API_V1_PREFIX}/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", REQUEST_ID_HEADER]
)

# Add request ID middleware
app.add_middleware(RequestIDMiddleware)

# Set up error handling
setup_error_handling(app)

# Set up logging
setup_logging()

# Set up metrics
setup_metrics()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(editor.router, tags=["editor"])
app.include_router(files.router, tags=["files"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(keys.router, tags=["keys"])
app.include_router(tags.router, tags=["tags"])
app.include_router(transcriber.router, tags=["transcriber"])
app.include_router(verify.router, tags=["verify"])
app.include_router(viewer.router, tags=["viewer"])
app.include_router(vocabulary.router, tags=["vocabulary"])
app.include_router(zip.router, tags=["zip"])

# Health check endpoint
@app.get("/health")
async def health_check(request: Request) -> ApiResponse[dict]:
    """Health check endpoint."""
    return ApiResponse(
        data={"status": "ok"},
        request_id=getattr(request.state, "request_id", None)
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    # Initialize services
    pass

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Run shutdown tasks."""
    # Cleanup services
    pass
