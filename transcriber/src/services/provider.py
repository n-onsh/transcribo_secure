import logging
from typing import Dict, Optional, Protocol
from pathlib import Path
import httpx
import os
from datetime import datetime
from pydantic_settings import BaseSettings
from .transcription import TranscriptionService

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

class TranscriptionServiceInterface(Protocol):
    """Interface for transcription service"""
    async def transcribe(self, file: Path, job_id: str) -> Dict:
        """Transcribe audio file"""
        ...

class BackendClientInterface(Protocol):
    """Interface for backend API client"""
    async def get_next_job(self) -> Optional[Dict]:
        """Get next available job"""
        ...
    
    async def download_file(self, file_id: str, temp_dir: Path) -> Path:
        """Download file from backend"""
        ...
    
    async def upload_results(self, job_id: str, results: Dict) -> None:
        """Upload transcription results"""
        ...
    
    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update job status"""
        ...

class BackendClient(BackendClientInterface):
    """Client for backend API"""
    def __init__(self, settings: Settings):
        self.settings = settings
        self.headers = {"X-Encryption-Key": os.getenv("ENCRYPTION_KEY", "")}

    async def get_next_job(self) -> Optional[Dict]:
        """Get next available job"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.settings.backend_api_url}/api/v1/jobs/next",
                    headers=self.headers
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

    async def download_file(self, file_id: str, temp_dir: Path) -> Path:
        """Download file from backend"""
        temp_file = temp_dir / f"{file_id}_input"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.settings.backend_api_url}/api/v1/files/{file_id}/download",
                timeout=None,
                headers=self.headers
            )
            response.raise_for_status()
            
            with open(temp_file, 'wb') as f:
                f.write(response.content)
        
        return temp_file

    async def upload_results(self, job_id: str, results: Dict) -> None:
        """Upload transcription results"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.backend_api_url}/api/v1/jobs/{job_id}/results",
                json=results,
                headers=self.headers
            )
            response.raise_for_status()

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """Update job status"""
        data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if error_message:
            data["error_message"] = error_message

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.settings.backend_api_url}/api/v1/jobs/{job_id}/status",
                json=data,
                headers=self.headers
            )
            response.raise_for_status()

class TranscriberServiceProvider:
    """Service provider for transcriber container"""
    def __init__(self):
        """Initialize service provider"""
        self._settings = None
        self._transcription = None
        self._backend = None
        self._initialized = False
        logger.info("Transcriber service provider initialized")

    async def initialize(self):
        """Initialize all services"""
        if self._initialized:
            return

        try:
            # Load settings
            self._settings = Settings()
            logger.info("Settings loaded")

            # Initialize transcription service
            self._transcription = TranscriptionService(
                device=self._settings.device,
                batch_size=self._settings.batch_size,
                hf_token=self._settings.hf_auth_token
            )
            logger.info("Transcription service initialized")

            # Initialize backend client
            self._backend = BackendClient(self._settings)
            logger.info("Backend client initialized")

            self._initialized = True
            logger.info("All services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Clean up all services"""
        try:
            # Clean up services if needed
            self._transcription = None
            self._backend = None
            self._settings = None
            self._initialized = False
            logger.info("Services cleaned up")

        except Exception as e:
            logger.error(f"Error cleaning up services: {str(e)}")
            raise

    @property
    def settings(self) -> Settings:
        """Get settings"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._settings

    @property
    def transcription(self) -> TranscriptionServiceInterface:
        """Get transcription service"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._transcription

    @property
    def backend(self) -> BackendClientInterface:
        """Get backend client"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._backend
