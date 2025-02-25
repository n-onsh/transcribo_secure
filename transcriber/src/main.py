import asyncio
import logging
from datetime import datetime
import httpx
import uuid
import socket
import json
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from pathlib import Path
import os
import tempfile
import shutil
from .utils import setup_telemetry
from fastapi import FastAPI, HTTPException, Response, BackgroundTasks
from .services.provider import TranscriberServiceProvider

# Configure logging first to minimize startup output
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app
app = FastAPI()

# Set up OpenTelemetry
setup_telemetry(app)

# Initialize instrumentors
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument()

# Get tracer and logger
tracer = trace.get_tracer(__name__)
logger = logs.get_logger(__name__)

# Global service provider
service_provider = TranscriberServiceProvider()

# Generate a unique instance ID for this transcriber
instance_id = f"{socket.gethostname()}-{uuid.uuid4()}"

# Health check status
is_healthy = True
is_ready = False

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not is_healthy:
        raise HTTPException(status_code=503, detail="Service unhealthy")
    return {"status": "healthy", "instance_id": instance_id}

@app.get("/ready")
async def ready_check():
    """Readiness check endpoint"""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {"status": "ready", "instance_id": instance_id}

@app.get("/metrics")
async def metrics():
    """Metrics endpoint for Prometheus"""
    return {}  # PrometheusMetricReader will handle the response

@app.get("/instance")
async def get_instance_info():
    """Get instance information"""
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
    """Process a job in the background"""
    if not is_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    
    # Start job processing in the background
    background_tasks.add_task(process_job_task, job_id)
    return {"status": "processing", "job_id": job_id, "instance_id": instance_id}

async def process_job_task(job_id: str):
    """Process a transcription job"""
    # Create a unique temporary directory for this job
    job_temp_dir = Path(tempfile.mkdtemp(prefix=f"transcriber-{job_id}-"))
    
    try:
        # Get job details
        job = await service_provider.backend.get_job(job_id)
        if not job:
            logger.emit(
                "Job not found",
                severity=Severity.ERROR,
                attributes={"job_id": job_id}
            )
            return
            
        file_id = job['file_id']
        language = job.get('language', 'de')  # Default to German if not specified
        vocabulary = job.get('vocabulary', [])
        
        logger.emit(
            "Processing job",
            severity=Severity.INFO,
            attributes={
                "job_id": job_id,
                "file_id": file_id,
                "instance_id": instance_id,
                "language": language
            }
        )

        # Update job status to processing
        await service_provider.backend.update_job_status(
            job_id, 
            "processing",
            {"instance_id": instance_id}
        )

        # Download file
        with tracer.start_span("download_file") as download_span:
            download_span.set_attribute("file_id", file_id)
            input_file = await service_provider.backend.download_file(file_id, job_temp_dir)
        
        # Perform transcription
        with tracer.start_span("transcribe") as transcribe_span:
            transcribe_span.set_attribute("job_id", job_id)
            transcription_result = await service_provider.transcription.transcribe(
                input_file,
                job_id=job_id,
                language=language,
                vocabulary=vocabulary
            )

        # Upload results
        with tracer.start_span("upload_results") as upload_span:
            upload_span.set_attribute("job_id", job_id)
            await service_provider.backend.upload_results(job_id, transcription_result)
        
        # Update job status to completed
        await service_provider.backend.update_job_status(
            job_id, 
            "completed",
            {"instance_id": instance_id}
        )
        
        logger.emit(
            "Job completed successfully",
            severity=Severity.INFO,
            attributes={
                "job_id": job_id,
                "instance_id": instance_id,
                "duration": transcription_result.get("duration", 0)
            }
        )
        
    except Exception as e:
        logger.emit(
            "Error processing job",
            severity=Severity.ERROR,
            attributes={
                "error": str(e),
                "job_id": job_id,
                "instance_id": instance_id
            }
        )
        
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
            logger.emit(
                "Failed to update job status",
                severity=Severity.ERROR,
                attributes={
                    "error": str(update_error),
                    "job_id": job_id
                }
            )
        
    finally:
        # Cleanup temporary directory
        try:
            shutil.rmtree(job_temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            logger.emit(
                "Failed to clean up temporary directory",
                severity=Severity.WARN,
                attributes={
                    "error": str(cleanup_error),
                    "job_id": job_id,
                    "temp_dir": str(job_temp_dir)
                }
            )

class TranscriberService:
    def __init__(self):
        """Initialize transcriber service"""
        self.running = False
        self.job_workers = []
        logger.emit(
            "Transcriber service initialized",
            severity=Severity.INFO,
            attributes={"instance_id": instance_id}
        )

    async def start(self):
        """Start the transcriber service"""
        global is_ready
        
        logger.emit(
            "Starting transcriber service",
            severity=Severity.INFO,
            attributes={"instance_id": instance_id}
        )
        
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
        """Stop the transcriber service"""
        global is_ready, is_healthy
        
        logger.emit(
            "Stopping transcriber service",
            severity=Severity.INFO,
            attributes={"instance_id": instance_id}
        )
        
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
        
        logger.emit(
            "Transcriber service stopped",
            severity=Severity.INFO,
            attributes={"instance_id": instance_id}
        )

    async def _job_worker(self, worker_id: str):
        """Worker task to process jobs"""
        logger.emit(
            "Job worker started",
            severity=Severity.INFO,
            attributes={
                "worker_id": worker_id,
                "instance_id": instance_id
            }
        )
        
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
                logger.emit(
                    "Job worker cancelled",
                    severity=Severity.INFO,
                    attributes={
                        "worker_id": worker_id,
                        "instance_id": instance_id
                    }
                )
                break
                
            except Exception as e:
                logger.emit(
                    "Error in job worker",
                    severity=Severity.ERROR,
                    attributes={
                        "error": str(e),
                        "worker_id": worker_id,
                        "instance_id": instance_id
                    }
                )
                await asyncio.sleep(service_provider.settings.poll_interval)

async def main():
    """Main entry point"""
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
        logger.emit(
            "Fatal error",
            severity=Severity.ERROR,
            attributes={"error": str(e)}
        )
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
