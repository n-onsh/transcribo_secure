import asyncio
import logging
from datetime import datetime
import httpx
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from pathlib import Path
import os
import tempfile
from .utils import setup_telemetry
from fastapi import FastAPI
from .services.provider import TranscriberServiceProvider

# Configure logging first to minimize startup output
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app for metrics endpoint
app = FastAPI()

# Set up OpenTelemetry
setup_telemetry(app)

# Initialize instrumentors
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument()

# Get tracer
tracer = trace.get_tracer(__name__)
logger = logging.getLogger(__name__)

# Global service provider
service_provider = TranscriberServiceProvider()

@app.get("/metrics")
async def metrics():
    """Metrics endpoint for Prometheus"""
    return {}  # PrometheusMetricReader will handle the response

# Start FastAPI in the background
import uvicorn
from threading import Thread
Thread(target=lambda: uvicorn.run(app, host="0.0.0.0", port=8000)).start()

class TranscriberService:
    def __init__(self):
        """Initialize transcriber service"""
        self.running = False
        logger.warning("Transcriber service initialized")

    async def start(self):
        """Start the transcriber service"""
        logger.warning("Starting transcriber service")
        self.running = True
        
        while self.running:
            try:
                # Poll for jobs
                job = await service_provider.backend.get_next_job()
                
                if job:
                    await self._process_job(job)
                else:
                    # No job available, wait before polling again
                    await asyncio.sleep(service_provider.settings.poll_interval)
                    
            except Exception as e:
                logger.error(f"Error in transcriber service: {str(e)}")
                await asyncio.sleep(service_provider.settings.poll_interval)

    async def _process_job(self, job: dict):
        """Process a transcription job"""
        job_id = job['job_id']
        file_id = job['file_id']
        
        logger.warning(f"Processing job {job_id} for file {file_id}")

        try:
            # Update job status to processing
            await service_provider.backend.update_job_status(job_id, "processing")

            # Create temporary directory for this job
            job_temp_dir = Path(service_provider.settings.temp_dir) / job_id
            job_temp_dir.mkdir(exist_ok=True)
            
            # Download file
            with tracer.start_span("download_file") as download_span:
                download_span.set_attribute("file_id", file_id)
                input_file = await service_provider.backend.download_file(file_id, job_temp_dir)
            
            # Perform transcription
            with tracer.start_span("transcribe") as transcribe_span:
                transcribe_span.set_attribute("job_id", job_id)
                transcription_result = await service_provider.transcription.transcribe(
                    input_file,
                    job_id=job_id
                )

            # Upload results
            with tracer.start_span("upload_results") as upload_span:
                upload_span.set_attribute("job_id", job_id)
                await service_provider.backend.upload_results(job_id, transcription_result)
            
            # Update job status to completed
            await service_provider.backend.update_job_status(job_id, "completed")
            
            logger.warning(f"Successfully completed job {job_id}")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {str(e)}")
            await service_provider.backend.update_job_status(
                job_id,
                "failed",
                error_message=str(e)
            )
            
        finally:
            # Cleanup temporary files
            if job_temp_dir.exists():
                for file in job_temp_dir.glob("*"):
                    file.unlink()
                job_temp_dir.rmdir()

async def main():
    """Main entry point"""
    try:
        # Initialize services
        await service_provider.initialize()
        
        # Start transcriber
        transcriber = TranscriberService()
        await transcriber.start()
        
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise
    finally:
        await service_provider.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
