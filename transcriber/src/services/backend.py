"""Backend client for transcriber service."""

import io
import json
import httpx
from typing import Dict, Optional, BinaryIO
from ..utils.logging import log_info, log_error, log_warning

class BackendClient:
    """Client for interacting with the backend API."""

    def __init__(self, base_url: str):
        """Initialize backend client."""
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=300.0)

    async def close(self):
        """Close the client."""
        await self.client.aclose()

    async def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job details from backend."""
        try:
            response = await self.client.get(f"/api/v1/jobs/{job_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            log_error(f"Error getting job {job_id}: {str(e)}")
            return None

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """Update job status in backend."""
        try:
            data = {"status": status}
            if metadata:
                data["metadata"] = metadata

            response = await self.client.patch(
                f"/api/v1/jobs/{job_id}",
                json=data
            )
            response.raise_for_status()
            return True
        except Exception as e:
            log_error(f"Error updating job {job_id} status: {str(e)}")
            return False

    async def download_file(self, file_id: str) -> Optional[BinaryIO]:
        """Download file from backend storage."""
        try:
            response = await self.client.get(
                f"/api/v1/files/{file_id}/download",
                follow_redirects=True
            )
            response.raise_for_status()
            
            # Convert response content to file-like object
            return io.BytesIO(response.content)
        except Exception as e:
            log_error(f"Error downloading file {file_id}: {str(e)}")
            return None

    async def upload_results(self, job_id: str, results: Dict) -> bool:
        """Upload transcription results to backend."""
        try:
            response = await self.client.post(
                f"/api/v1/jobs/{job_id}/results",
                json=results
            )
            response.raise_for_status()
            return True
        except Exception as e:
            log_error(f"Error uploading results for job {job_id}: {str(e)}")
            return False
