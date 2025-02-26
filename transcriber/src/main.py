"""Transcriber service."""

import asyncio
import logging
from datetime import datetime
import httpx
import uuid
import socket
import json
from pathlib import Path
import os
import tempfile
import shutil
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from prometheus_client import make_asgi_app
from .services.provider import TranscriberServiceProvider
from .utils import setup_metrics
from .utils.metrics import (
    PROCESSING_DURATION,
    PROCESSING_TOTAL,
    PROCESSING_ERRORS,
    MODEL_LOAD_TIME,
    MODEL_INFERENCE_TIME,
    QUEUE_SIZE,
    QUEUE_WAIT_TIME,
    track_processing,
    track_model_load,
    track_inference,
    track_queue_metrics
)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app
app = FastAPI()

# Create metrics app
metrics_app = make_asgi_app()

# Mount metrics endpoint
app.mount("/metrics", metrics_app)

# Set up metrics
setup_metrics()

# Global service provider
service_provider = TranscriberServiceProvider()

# Generate a unique instance ID for this transcriber
instance_id = f"{socket.gethostname()}-{uuid.uuid4()}"

# Health check status
is_healthy = True
is_ready = False

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    if not is_healthy:
        raise HTTPException(status_code=503, detail="Service unhealthy")
    return {"status": "healthy", "instance_id": instance_id}

@app.get("/ready")
async def ready_check():
    """Readiness check endpoint."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ready", "instance_id": instance_id}

@app.get("/instance")
async def get_instance_info():
    """Get instance information."""
    return {
        "instance_id": instance_id,
        "hostname": socket.gethostname(),
        "is_ready": is_ready,
        "is_healthy": is_healthy,
        "device": service_provider.settings.device,
        "batch_size": service_provider.settings.batch_size
    }

@app.post("/jobs/{job_id}/process")
async def process_job(job_id: str, background_tasks: BackgroundTasks):
    """Process a job in the background."""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Start job processing in the background
    background_tasks.add_task(process_job_task, job_id)
    return {"status": "processing", "job_id": job_id, "instance_id": instance_id}

async def process_job_task(job_id: str):
    """Process a transcription job."""
    # Create a unique temporary directory for this job
    job_temp_dir = Path(tempfile.mkdtemp(prefix=f"transcriber-{job_id}-"))
    start_time = datetime.utcnow()
    
    try:
        # Get job details
        job = await service_provider.backend.get_job(job_id)
        if not job:
            logging.error(f"Job not found: {job_id}")
            return
            
        file_id = job['file_id']
        language = job.get('language', 'de')  # Default to German if not specified
        vocabulary = job.get('vocabulary', [])
        
        logging.info(f"Processing job {job_id} for file {file_id}")

        # Update job status to processing
        await service_provider.backend.update_job_status(
            job_id, 
            "processing",
            {"instance_id": instance_id}
        )

        # Download file
        input_file = await service_provider.backend.download_file(file_id, job_temp_dir)
        
        # Perform transcription
        transcription_result = await service_provider.transcription.transcribe(
            input_file,
            job_id=job_id,
            language=language,
            vocabulary=vocabulary
        )

        # Upload results
        await service_provider.backend.upload_results(job_id, transcription_result)
        
        # Update job status to completed
        await service_provider.backend.update_job_status(
            job_id, 
            "completed",
            {"instance_id": instance_id}
        )
        
        # Track successful processing
        duration = (datetime.utcnow() - start_time).total_seconds()
        track_processing(duration, True)
        logging.info(f"Job {job_id} completed successfully in {duration:.2f}s")
        
    except Exception as e:
        # Track failed processing
        duration = (datetime.utcnow() - start_time).total_seconds()
        track_processing(duration, False)
        logging.error(f"Error processing job {job_id}: {str(e)}")
        
        # Update job status to failed
        try:
            await service_provider.backend.update_job_status(
                job_id,
                "failed",
                {
                    "error_message": str(e),
                    "instance_id": instance_id
                }
            )
        except Exception as update_error:
            logging.error(f"Failed to update job status for {job_id}: {str(update_error)}")
        
    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(job_temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            logging.warning(f"Failed to clean up temporary directory for job {job_id}: {str(cleanup_error)}")

class TranscriberService:
    def __init__(self):
        """Initialize transcriber service."""
        self.running = False
        self.job_workers = []
        logging.info("Transcriber service initialized")

    async def start(self):
        """Start the transcriber service."""
        global is_ready
        
        logging.info("Starting transcriber service")
        
        self.running = True
        
        # Start worker tasks
        worker_count = int(os.getenv("WORKER_COUNT", "1"))
        for i in range(worker_count):
            worker = asyncio.create_task(self._job_worker(f"worker-{i}"))
            self.job_workers.append(worker)
        
        # Mark service as ready
        is_ready = True
        
        # Wait for workers to complete
        await asyncio.gather(*self.job_workers, return_exceptions=True)

    async def stop(self):
        """Stop the transcriber service."""
        global is_ready, is_healthy
        
        logging.info("Stopping transcriber service")
        
        # Mark service as not ready and unhealthy
        is_ready = False
        is_healthy = False
        
        # Stop running
        self.running = False
        
        # Cancel all workers
        for worker in self.job_workers:
            worker.cancel()
        
        # Wait for workers to complete
        await asyncio.gather(*self.job_workers, return_exceptions=True)
        
        logging.info("Transcriber service stopped")

    async def _job_worker(self, worker_id: str):
        """Worker task to process jobs."""
        logging.info(f"Job worker {worker_id} started")
        
        while self.running:
            try:
                # Try to claim a job with distributed locking
                job = await service_provider.backend.claim_job(instance_id)
                
                if job:
                    # Process job
                    await process_job_task(job['job_id'])
                else:
                    # No job available, wait before polling again
                    await asyncio.sleep(service_provider.settings.poll_interval)
                    
            except asyncio.CancelledError:
                logging.info(f"Job worker {worker_id} cancelled")
                break
                
            except Exception as e:
                logging.error(f"Error in job worker {worker_id}: {str(e)}")
                await asyncio.sleep(service_provider.settings.poll_interval)

async def main():
    """Main entry point."""
    global is_healthy
    
    try:
        # Initialize services
        await service_provider.initialize()
        
        # Start transcriber
        transcriber = TranscriberService()
        
        # Start FastAPI in the background
        import uvicorn
        config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="warning")
        server = uvicorn.Server(config)
        
        # Run both the transcriber and the API server
        await asyncio.gather(
            transcriber.start(),
            server.serve()
        )
        
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        is_healthy = False
        raise
        
    finally:
        # Clean up
        await service_provider.cleanup()

if __name__ == "__main__":
    # Set up signal handlers
    import signal
    
    loop = asyncio.get_event_loop()
    
    # Handle termination signals
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(service_provider.cleanup()))
    
    # Run the main function
    asyncio.run(main())
