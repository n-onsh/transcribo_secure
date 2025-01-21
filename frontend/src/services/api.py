import httpx
import logging
from typing import Optional, Dict, List
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class APIService:
    def __init__(self):
        self.base_url = os.getenv("BACKEND_API_URL", "http://localhost:8080/api/v1")
        self.timeout = httpx.Timeout(timeout=30.0)

    async def upload_file(self, file_path: Path, user_id: str) -> Dict:
        """Upload file to backend API"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                files = {'file': open(file_path, 'rb')}
                params = {'user_id': user_id}
                response = await client.post(
                    f"{self.base_url}/files/",
                    files=files,
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error uploading file: {str(e)}")
            raise

    async def get_file_status(self, file_id: str) -> Dict:
        """Get file status from backend"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/files/{file_id}"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting file status: {str(e)}")
            raise

    async def get_user_jobs(
        self,
        user_id: str,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Get jobs for a user"""
        try:
            params = {'status': status} if status else {}
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/jobs/user/{user_id}",
                    params=params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting user jobs: {str(e)}")
            raise

    async def get_transcription_result(self, job_id: str) -> Dict:
        """Get transcription results"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/jobs/{job_id}/results"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting transcription results: {str(e)}")
            raise

    async def retry_job(self, job_id: str) -> Dict:
        """Retry a failed job"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/jobs/{job_id}/retry"
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error retrying job: {str(e)}")
            raise