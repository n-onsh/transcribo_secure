"""Main entry point for transcriber service."""

import asyncio
import logging
import os
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from prometheus_client import make_asgi_app
from .services.provider import TranscriberServiceProvider
from .utils import setup_metrics
from .utils.logging import log_info, log_error, log_warning
from .utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    MODEL_LOAD_TIME,
    MODEL_INFERENCE_TIME,
    MEMORY_USAGE,
    track_transcription,
    track_transcription_error,
    track_model_load,
    track_model_inference,
    track_memory_usage
)

# Create FastAPI app
app = FastAPI()

# Create metrics app
metrics_app = make_asgi_app()

# Mount metrics endpoint
app.mount("/metrics", metrics_app)

# Global service provider
service_provider = TranscriberServiceProvider()

# Health check status
is_healthy = True
is_ready = False

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not is_healthy:
        raise HTTPException(status_code=503, detail="Service unhealthy")
    return {"status": "healthy"}

@app.get("/ready")
async def ready_check():
    """Readiness check endpoint."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ready"}

@app.post("/jobs/{job_id}/process")
async def process_job(job_id: str, background_tasks: BackgroundTasks):
    """Process a job in the background."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Start job processing in the background
    background_tasks.add_task(process_job_task, job_id)
    return {"status": "processing", "job_id": job_id}

async def process_job_task(job_id: str):
    """Process a transcription job."""
    try:
        # Get job details from backend
        job = await service_provider.backend.get_job(job_id)
        if not job:
            log_error(f"Job not found: {job_id}")
            return
            
        file_id = job['file_id']
        language = job.get('language', 'de')  # Default to German if not specified
        vocabulary = job.get('vocabulary', [])
        
        log_info(f"Processing job {job_id} for file {file_id}")

        # Update job status to processing
        await service_provider.backend.update_job_status(
            job_id, 
            "processing"
        )

        # Download file from storage
        audio_file = await service_provider.backend.download_file(file_id)
        
        # Perform transcription
        transcription_result = await service_provider.transcription.transcribe(
            audio_file,
            job_id=job_id,
            language=language,
            vocabulary=vocabulary
        )

        # Upload results back to storage
        await service_provider.backend.upload_results(job_id, transcription_result)
        
        # Update job status to completed
        await service_provider.backend.update_job_status(
            job_id, 
            "completed"
        )
        
        log_info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        log_error(f"Error processing job {job_id}: {str(e)}")
        
        # Update job status to failed
        try:
            await service_provider.backend.update_job_status(
                job_id,
                "failed",
                {"error_message": str(e)}
            )
        except Exception as update_error:
            log_error(f"Failed to update job status for {job_id}: {str(update_error)}")

async def startup():
    """Initialize services on startup."""
    global is_ready
    
    try:
        # Initialize services
        await service_provider.initialize()
        
        # Mark service as ready
        is_ready = True
        log_info("Transcriber service ready")
        
    except Exception as e:
        log_error(f"Failed to initialize transcriber service: {str(e)}")
        raise

async def shutdown():
    """Clean up services on shutdown."""
    global is_ready, is_healthy
    
    try:
        # Mark service as not ready and unhealthy
        is_ready = False
        is_healthy = False
        
        # Clean up services
        await service_provider.cleanup()
        log_info("Transcriber service shut down")
        
    except Exception as e:
        log_error(f"Error during transcriber service shutdown: {str(e)}")
        raise

# Register startup and shutdown handlers
app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)

if __name__ == "__main__":
    import uvicorn
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the FastAPI application
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
