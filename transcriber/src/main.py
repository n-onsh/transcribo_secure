import asyncio
import logging
from datetime import datetime
import httpx
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from .services.transcription import TranscriptionService
from pathlib import Path
import os
from typing import Optional, Any
import json
from pydantic_settings import BaseSettings
import tempfile

# Configure OpenTelemetry
resource = Resource.create({"service.name": "transcriber"})
tracer_provider = TracerProvider(resource=resource)
otlp_exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318/v1/traces"))
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
trace.set_tracer_provider(tracer_provider)

# Initialize instrumentors
HTTPXClientInstrumentor().instrument()
LoggingInstrumentor().instrument()

# Get tracer
tracer = trace.get_tracer(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    # Application settings
    backend_api_url: str
    poll_interval: int = 5  # seconds
    max_retries: int = 3
    temp_dir: str = "/tmp/transcriber"
    hf_auth_token: str
    device: str
    batch_size: int

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in environment

class TranscriberService:
    def __init__(self):
        self.settings = Settings()
        self.transcription_service = TranscriptionService(
            device=self.settings.device,
            batch_size=self.settings.batch_size,
            hf_token=self.settings.hf_auth_token
        )
        self.temp_dir = Path(self.settings.temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.running = False

    async def start(self):
        """Start the transcriber service"""
        logger.info("Starting transcriber service")
        self.running = True
        
        while self.running:
            try:
                # Poll for jobs
                job = await self._get_next_job()
                
                if job:
                    await self._process_job(job)
                else:
                    # No job available, wait before polling again
                    await asyncio.sleep(self.settings.poll_interval)
                    
            except Exception as e:
                logger.error(f"Error in transcriber service: {str(e)}")
                await asyncio.sleep(self.settings.poll_interval)

    async def _get_next_job(self) -> Optional[dict]:
        """Poll the backend API for the next available job"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.settings.backend_api_url}/jobs/next"
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    logger.error(f"Error polling for jobs: {response.text}")
                    return None
        except Exception as e:
            logger.error(f"Error polling for jobs: {str(e)}")
            return None

    async def _process_job(self, job: dict):
        """Process a transcription job"""
        job_id = job['job_id']
        file_id = job['file_id']
        
        job_temp_dir = self.temp_dir / job_id
        
        with tracer.start_as_current_span("process_job") as span:
            span.set_attribute("job_id", job_id)
            span.set_attribute("file_id", file_id)
            logger.info(f"Processing job {job_id} for file {file_id}")

            try:
                # Update job status to processing
                await self._update_job_status(job_id, "processing")

                # Create temporary directory for this job
                job_temp_dir.mkdir(exist_ok=True)
                
                # Download file
                with tracer.start_span("download_file") as download_span:
                    download_span.set_attribute("file_id", file_id)
                    input_file = await self._download_file(file_id, job_temp_dir)
                
                # Perform transcription
                with tracer.start_span("transcribe") as transcribe_span:
                    transcribe_span.set_attribute("job_id", job_id)
                    transcription_result = await self.transcription_service.transcribe(
                        input_file,
                        job_id=job_id
                    )

                # Upload results
                with tracer.start_span("upload_results") as upload_span:
                    upload_span.set_attribute("job_id", job_id)
                    await self._upload_results(job_id, transcription_result)
                
                # Update job status to completed
                await self._update_job_status(job_id, "completed")
                
                logger.info(f"Successfully completed job {job_id}")
                
            except Exception as e:
                logger.error(f"Error processing job {job_id}: {str(e)}")
                await self._update_job_status(
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

    async def _download_file(self, file_id: str, temp_dir: Path) -> Path:
        """Download file from backend API"""
        temp_file = temp_dir / f"{file_id}_input"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.settings.backend_api_url}/files/{file_id}/download",
                timeout=None
            )
            response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                f.write(response.content)
        
        return temp_file

    async def _upload_results(self, job_id: str, results: dict):
        """Upload transcription results to backend API"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.backend_api_url}/jobs/{job_id}/results",
                json=results
            )
            response.raise_for_status()

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """Update job status in backend API"""
        data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if error_message:
            data["error_message"] = error_message

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.backend_api_url}/jobs/{job_id}/status",
                json=data
            )
            response.raise_for_status()

async def main():
    """Main entry point"""
    transcriber = TranscriberService()
    await transcriber.start()

if __name__ == "__main__":
    asyncio.run(main())
