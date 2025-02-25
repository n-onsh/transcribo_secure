import logging
from typing import Dict, Optional, Protocol, List
from pathlib import Path
import httpx
import os
import uuid
from datetime import datetime
from pydantic_settings import BaseSettings
from opentelemetry import logs
from opentelemetry.logs import Severity
from .transcription import TranscriptionService

logger = logs.get_logger(__name__)

class Settings(BaseSettings):
    # Application settings
    backend_api_url: str
    poll_interval: int = 5  # seconds
    max_retries: int = 3
    temp_dir: str = "/tmp/transcriber"
    hf_auth_token: str
    device: str
    batch_size: int
    worker_count: int = 1
    supported_languages: List[str] = ["de", "en", "fr", "it"]  # Supported languages
    default_language: str = "de"  # Default language

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Allow extra fields in environment

class TranscriptionServiceInterface(Protocol):
    """Interface for transcription service"""
    async def transcribe(
        self,
        file: Path,
        job_id: str,
        language: Optional[str] = None,
        vocabulary: Optional[List[str]] = None
    ) -> Dict:
        """Transcribe audio file"""
        ...

class BackendClientInterface(Protocol):
    """Interface for backend API client"""
    async def get_next_job(self) -> Optional[Dict]:
        """Get next available job"""
        ...
    
    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        ...
    
    async def claim_job(self, instance_id: str) -> Optional[Dict]:
        """Claim a job with distributed locking"""
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
        metadata: Optional[Dict] = None
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

    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job by ID"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.settings.backend_api_url}/api/v1/jobs/{job_id}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    logger.emit(
                        "Error getting job",
                        severity=Severity.ERROR,
                        attributes={
                            "job_id": job_id,
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                    return None
        except Exception as e:
            logger.emit(
                "Error getting job",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "job_id": job_id
                }
            )
            return None

    async def claim_job(self, instance_id: str) -> Optional[Dict]:
        """Claim a job with distributed locking"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.settings.backend_api_url}/api/v1/jobs/claim",
                    json={"instance_id": instance_id},
                    headers=self.headers
                )
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    return None
                else:
                    logger.emit(
                        "Error claiming job",
                        severity=Severity.ERROR,
                        attributes={
                            "instance_id": instance_id,
                            "status_code": response.status_code,
                            "response": response.text
                        }
                    )
                    return None
        except Exception as e:
            logger.emit(
                "Error claiming job",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "instance_id": instance_id
                }
            )
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
        metadata: Optional[Dict] = None
    ) -> None:
        """Update job status"""
        data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }
        if metadata:
            data.update(metadata)

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
        logger.emit(
            "Transcriber service provider initialized",
            severity=Severity.INFO
        )

    async def initialize(self):
        """Initialize all services"""
        if self._initialized:
            return

        try:
            # Load settings
            self._settings = Settings()
            logger.emit(
                "Settings loaded",
                severity=Severity.INFO,
                attributes={
                    "device": self._settings.device,
                    "batch_size": self._settings.batch_size,
                    "worker_count": self._settings.worker_count,
                    "supported_languages": self._settings.supported_languages
                }
            )

            # Initialize transcription service
            self._transcription = TranscriptionService(
                device=self._settings.device,
                batch_size=self._settings.batch_size,
                hf_token=self._settings.hf_auth_token
            )
            logger.emit(
                "Transcription service initialized",
                severity=Severity.INFO
            )

            # Initialize backend client
            self._backend = BackendClient(self._settings)
            logger.emit(
                "Backend client initialized",
                severity=Severity.INFO
            )

            self._initialized = True
            logger.emit(
                "All services initialized",
                severity=Severity.INFO
            )

        except Exception as e:
            logger.emit(
                "Failed to initialize services",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
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
            logger.emit(
                "Services cleaned up",
                severity=Severity.INFO
            )

        except Exception as e:
            logger.emit(
                "Error cleaning up services",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
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
