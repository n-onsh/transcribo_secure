"""Vocabulary service."""

import re
from typing import Dict, List, Optional
from ..utils.logging import log_info, log_error
from .job_manager import JobManager
from .transcription import TranscriptionService
from .interfaces import VocabularyInterface

class VocabularyService(VocabularyInterface):
    """Service for managing custom vocabulary."""

    def __init__(self, job_manager: JobManager, transcription_service: TranscriptionService):
        """Initialize vocabulary service."""
        self.job_manager = job_manager
        self.transcription_service = transcription_service
        self.initialized = False
        self._vocabulary_store = {}  # In-memory store for demo, would be DB in production

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize dependencies
            self.initialized = True
            log_info("Vocabulary service initialized")

        except Exception as e:
            log_error(f"Failed to initialize vocabulary service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Vocabulary service cleaned up")

        except Exception as e:
            log_error(f"Error during vocabulary service cleanup: {str(e)}")
            raise

    async def apply_vocabulary_to_job(self, job_id: str, vocabulary_items: List[Dict]) -> bool:
        """Apply custom vocabulary to a transcription job."""
        try:
            # Get job
            job = await self.job_manager.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Store vocabulary items for this job
            await self.store_job_vocabulary(job_id, vocabulary_items)
            
            # If job is already completed, apply vocabulary to existing transcription
            if job.status == "completed":
                transcription = await self.transcription_service.get_transcription(job.file_id)
                updated_transcription = await self.apply_vocabulary_to_transcription(
                    transcription, vocabulary_items
                )
                await self.transcription_service.save_transcription(job.file_id, updated_transcription)
            
            return True
        except Exception as e:
            log_error(f"Error applying vocabulary to job {job_id}: {str(e)}")
            return False

    async def store_job_vocabulary(self, job_id: str, vocabulary_items: List[Dict]) -> None:
        """Store vocabulary items for a job."""
        try:
            # Store in memory (would be DB in production)
            self._vocabulary_store[job_id] = vocabulary_items
            log_info(f"Stored vocabulary items for job {job_id}")
        except Exception as e:
            log_error(f"Error storing vocabulary for job {job_id}: {str(e)}")
            raise

    async def apply_vocabulary_to_transcription(
        self, transcription: Dict, vocabulary_items: List[Dict]
    ) -> Dict:
        """Apply vocabulary items to an existing transcription."""
        try:
            # Create a mapping of terms to replacements
            replacements = {item["term"]: item["replacement"] for item in vocabulary_items}
            
            # Apply replacements to each segment
            for segment in transcription.get("segments", []):
                text = segment.get("text", "")
                for term, replacement in replacements.items():
                    # Case-insensitive replacement
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    text = pattern.sub(replacement, text)
                segment["text"] = text
            
            return transcription
        except Exception as e:
            log_error(f"Error applying vocabulary to transcription: {str(e)}")
            raise

    async def get_job_vocabulary(self, job_id: str) -> List[Dict]:
        """Get vocabulary items for a job."""
        try:
            # Retrieve from memory (would be DB in production)
            return self._vocabulary_store.get(job_id, [])
        except Exception as e:
            log_error(f"Error getting vocabulary for job {job_id}: {str(e)}")
            raise

    async def delete_job_vocabulary(self, job_id: str) -> bool:
        """Delete vocabulary items for a job."""
        try:
            # Remove from memory (would be DB in production)
            if job_id in self._vocabulary_store:
                del self._vocabulary_store[job_id]
                log_info(f"Deleted vocabulary items for job {job_id}")
                return True
            return False
        except Exception as e:
            log_error(f"Error deleting vocabulary for job {job_id}: {str(e)}")
            raise
