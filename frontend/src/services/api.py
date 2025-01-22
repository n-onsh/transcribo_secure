# services/api.py
import os
import httpx
import logging
from typing import Optional, Dict, List, Union
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class APIService:
    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        # Let .env override the default
        self.base_url = base_url or os.getenv("BACKEND_API_URL", "http://localhost:8080/api/v1")
        self.timeout = httpx.Timeout(timeout=timeout)

    #
    # === Uploading/Files ===
    #
    async def upload_file(self, file_content: bytes, file_name: str, user_id: str) -> Dict:
        """
        Upload file to backend API.
        (This version accepts raw bytes and filename, so we don't need a temp file.)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Construct a "file" for multipart/form-data
                files = {'file': (file_name, file_content)}
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
        """Get file status from backend."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/files/{file_id}")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting file status: {str(e)}")
            raise

    async def get_job_media(self, job_id: str) -> bytes:
        """Get media file for a job."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/files/{job_id}/media")
                response.raise_for_status()
                return response.content
        except Exception as e:
            logger.error(f"Error getting job media: {str(e)}")
            raise

    #
    # === Jobs ===
    #
    async def get_user_jobs(self, user_id: str, status: Optional[str] = None) -> List[Dict]:
        """Get jobs for a user."""
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

    async def retry_job(self, job_id: str) -> Dict:
        """Retry a failed job."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/jobs/{job_id}/retry")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error retrying job: {str(e)}")
            raise

    async def get_transcription_result(self, job_id: str) -> Dict:
        """Get transcription results for a completed job."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/jobs/{job_id}/results")
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting transcription result: {str(e)}")
            raise

    #
    # === Editor ===
    #
    async def get_editor_content(self, job_id: str) -> Dict:
        """Get editor content for a job."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/jobs/{job_id}/viewer")
                response.raise_for_status()
                # If your backend returns raw text, we wrap it in a dict
                return {"content": response.text}
        except Exception as e:
            logger.error(f"Error getting editor content: {str(e)}")
            raise

    async def save_editor_content(self, job_id: str, content: str) -> Dict:
        """Save editor content changes."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/jobs/{job_id}/viewer/save",
                    json={"content": content}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error saving editor content: {str(e)}")
            raise

    #
    # === Exporting ===
    #
    async def export_srt(self, job_id: str) -> str:
        """Export job results as SRT."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/jobs/{job_id}/export/srt")
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error exporting SRT: {str(e)}")
            raise

    async def export_text(self, job_id: str) -> str:
        """Export job results as plain text."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/jobs/{job_id}/export/text")
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error exporting text: {str(e)}")
            raise
