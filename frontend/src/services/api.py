import httpx
import os
from typing import Optional, Dict, Any, BinaryIO, List
import logging
from .auth import AuthService

logger = logging.getLogger(__name__)

class APIService:
    def __init__(self, base_url: str, auth_service: AuthService):
        """Initialize API service with authentication"""
        self.base_url = base_url
        self.auth_service = auth_service
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=True
        )

    async def cleanup(self):
        """Clean up resources"""
        try:
            if self._client:
                await self._client.aclose()
                self._client = None
            logger.info("API service cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up API service: {str(e)}")
            raise

    async def _get_headers(self) -> Dict[str, str]:
        """Get headers with authentication token"""
        token = await self.auth_service.get_token()
        if not token:
            raise ValueError("Not authenticated")
        
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

    async def upload_file(
        self,
        file: BinaryIO,
        file_name: str,
        language: Optional[str] = None,
        vocabulary: Optional[List[str]] = None
    ) -> Dict:
        """Upload file with authentication and language selection"""
        try:
            headers = await self._get_headers()
            files = {"file": (file_name, file)}
            
            # Add language and vocabulary params
            params = {}
            if language:
                params["language"] = language
            if vocabulary:
                params["vocabulary"] = ",".join(vocabulary)
            
            response = await self._client.post(
                f"{self.base_url}/files/",
                headers=headers,
                files=files,
                params=params
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token expired or invalid, try to re-authenticate
                await self.auth_service.login()
            logger.error(f"HTTP error during file upload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"File upload failed: {str(e)}")
            raise

    async def get_jobs(self, language: Optional[str] = None) -> List[Dict]:
        """Get user's jobs with authentication and optional language filter"""
        try:
            headers = await self._get_headers()
            
            # Add language filter
            params = {}
            if language:
                params["language"] = language
            
            response = await self._client.get(
                f"{self.base_url}/jobs/",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error getting jobs: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get jobs: {str(e)}")
            raise

    async def get_file(self, file_id: str) -> BinaryIO:
        """Get file with authentication"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.get(
                f"{self.base_url}/files/{file_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.content
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error getting file: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get file: {str(e)}")
            raise

    async def get_transcription(self, job_id: str) -> Dict:
        """Get transcription results with authentication"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.get(
                f"{self.base_url}/transcriber/{job_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error getting transcription: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get transcription: {str(e)}")
            raise

    async def save_vocabulary(self, words: List[str]) -> Dict:
        """Save vocabulary with authentication"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.post(
                f"{self.base_url}/vocabulary",
                headers=headers,
                json={"words": words}
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error saving vocabulary: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to save vocabulary: {str(e)}")
            raise

    async def get_vocabulary(self) -> List[str]:
        """Get vocabulary with authentication"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.get(
                f"{self.base_url}/vocabulary",
                headers=headers
            )
            response.raise_for_status()
            return response.json().get("words", [])
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error getting vocabulary: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to get vocabulary: {str(e)}")
            raise

    # Editor-specific endpoints
    async def save_transcription(self, job_id: str) -> Dict:
        """Save transcription changes"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.post(
                f"{self.base_url}/transcriber/{job_id}/save",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error saving transcription: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to save transcription: {str(e)}")
            raise

    async def update_speaker(self, job_id: str, speaker_idx: int, name: str) -> Dict:
        """Update speaker name"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.put(
                f"{self.base_url}/transcriber/{job_id}/speakers/{speaker_idx}",
                headers=headers,
                json={"name": name}
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error updating speaker: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to update speaker: {str(e)}")
            raise

    async def update_segment(self, job_id: str, segment_id: str, data: Dict) -> Dict:
        """Update segment data"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.put(
                f"{self.base_url}/transcriber/{job_id}/segments/{segment_id}",
                headers=headers,
                json=data
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error updating segment: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to update segment: {str(e)}")
            raise

    async def delete_segment(self, job_id: str, segment_id: str) -> Dict:
        """Delete a segment"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.delete(
                f"{self.base_url}/transcriber/{job_id}/segments/{segment_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error deleting segment: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to delete segment: {str(e)}")
            raise

    async def add_segment(self, job_id: str, after_id: str) -> Dict:
        """Add a new segment after the specified one"""
        try:
            headers = await self._get_headers()
            
            response = await self._client.post(
                f"{self.base_url}/transcriber/{job_id}/segments",
                headers=headers,
                json={"after_id": after_id}
            )
            response.raise_for_status()
            return response.json()
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                await self.auth_service.login()
            logger.error(f"HTTP error adding segment: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to add segment: {str(e)}")
            raise
