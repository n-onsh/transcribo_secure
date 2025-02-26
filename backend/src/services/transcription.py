"""Transcription service."""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, cast
from datetime import datetime
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import StorageError, TranscriptionError, TranscriboError
from ..types import (
    ServiceConfig,
    ErrorContext,
    TranscriptionData,
    TranscriptionSegment,
    SpeakerInfo,
    FileID,
    JobID
)
from .base import BaseService
from .storage import StorageService
from .job_manager import JobManager
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    track_transcription,
    track_transcription_error
)

class TranscriptionService(BaseService):
    """Service for managing transcriptions."""

    def __init__(
        self,
        settings: ServiceConfig,
        storage_service: Optional[StorageService] = None,
        job_service: Optional[JobManager] = None
    ) -> None:
        """Initialize transcription service.
        
        Args:
            settings: Service configuration
            storage_service: Optional storage service instance
            job_service: Optional job manager instance
        """
        super().__init__(settings)
        self.storage: Optional[StorageService] = storage_service
        self.job_service: Optional[JobManager] = job_service
        self.storage_path: Path = Path('/tmp/transcriptions')
        self.max_file_size: int = 1073741824  # 1GB

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize storage if not provided
            if not self.storage:
                self.storage = StorageService(self.settings)
                await self.storage.initialize()

            # Initialize settings
            self.storage_path = Path(self.settings.get('storage_path', '/tmp/transcriptions'))
            self.max_file_size = int(self.settings.get('max_file_size', 1073741824))  # 1GB
            
            # Ensure storage directory exists
            self.storage_path.mkdir(parents=True, exist_ok=True)

            log_info("Transcription service initialized")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_transcription",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize transcription service: {str(e)}")
            raise TranscriboError(
                "Failed to initialize transcription service",
                details=error_context
            )

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
        try:
            log_info("Transcription service cleaned up")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_transcription",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during transcription service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up transcription service",
                details=error_context
            )

    async def get_transcription(self, file_id: FileID) -> TranscriptionData:
        """Get transcription data.
        
        Args:
            file_id: File ID to get transcription for
            
        Returns:
            Transcription data
            
        Raises:
            TranscriptionError: If transcription retrieval fails
        """
        try:
            self._check_initialized()

            # Track operation start
            start_time = logging.time()
            
            # Get transcription file path
            file_path = self._get_transcription_path(file_id)
            
            # Read transcription data
            if not self.storage:
                raise TranscriptionError("Storage service not initialized")

            data = await self.storage.get_file(str(file_path))
            if not data:
                raise TranscriptionError(f"Transcription not found for file {file_id}")
            
            # Parse JSON data
            try:
                transcription = cast(TranscriptionData, json.loads(data.decode('utf-8')))
            except json.JSONDecodeError as e:
                raise TranscriptionError(f"Invalid transcription data: {str(e)}")
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Retrieved transcription for file {file_id}")
            return transcription
            
        except StorageError as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "get_transcription",
                "resource_id": file_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Storage error getting transcription for file {file_id}: {str(e)}")
            raise TranscriptionError("Failed to get transcription", details=error_context)
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "get_transcription",
                "resource_id": file_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error getting transcription for file {file_id}: {str(e)}")
            raise TranscriptionError("Failed to get transcription", details=error_context)

    async def save_transcription(
        self,
        file_id: FileID,
        transcription: TranscriptionData
    ) -> None:
        """Save transcription data.
        
        Args:
            file_id: File ID to save transcription for
            transcription: Transcription data to save
            
        Raises:
            TranscriptionError: If transcription save fails
        """
        try:
            self._check_initialized()

            # Track operation start
            start_time = logging.time()
            
            # Get transcription file path
            file_path = self._get_transcription_path(file_id)
            
            # Convert transcription to JSON
            try:
                data = json.dumps(transcription, ensure_ascii=False, indent=2).encode('utf-8')
            except Exception as e:
                raise TranscriptionError(f"Invalid transcription data: {str(e)}")
            
            # Save transcription data
            if not self.storage:
                raise TranscriptionError("Storage service not initialized")

            await self.storage.store_file(str(file_path), data)
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Saved transcription for file {file_id}")
            
        except StorageError as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "save_transcription",
                "resource_id": file_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Storage error saving transcription for file {file_id}: {str(e)}")
            raise TranscriptionError("Failed to save transcription", details=error_context)
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "save_transcription",
                "resource_id": file_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error saving transcription for file {file_id}: {str(e)}")
            raise TranscriptionError("Failed to save transcription", details=error_context)

    def _get_transcription_path(self, file_id: FileID) -> Path:
        """Get path for transcription file.
        
        Args:
            file_id: File ID to get path for
            
        Returns:
            Path to transcription file
        """
        # Use first 2 characters of file ID for subdirectory to avoid too many files in one directory
        subdir = file_id[:2]
        return self.storage_path / subdir / f"{file_id}.json"

    async def update_speakers(
        self,
        job_id: JobID,
        speakers: List[SpeakerInfo]
    ) -> TranscriptionData:
        """Update speaker information for a transcription.
        
        Args:
            job_id: Job ID to update speakers for
            speakers: List of speaker information
            
        Returns:
            Updated transcription data
            
        Raises:
            TranscriptionError: If speaker update fails
        """
        try:
            self._check_initialized()

            # Track operation start
            start_time = logging.time()
            
            # Validate speakers data
            if not all(s.get("id") and s.get("name") for s in speakers):
                raise TranscriptionError("Invalid speaker data: missing id or name")
            
            # Get job
            if not self.job_service:
                raise TranscriptionError("Job service not initialized")

            try:
                job = await self.job_service.get_job_status(job_id)
                if not job:
                    raise TranscriptionError(f"Job {job_id} not found")
            except Exception as e:
                raise TranscriptionError(f"Failed to get job: {str(e)}")
            
            # Get transcription
            file_id = cast(FileID, job.get('file_id'))
            transcription = await self.get_transcription(file_id)
            
            # Update speaker information
            speaker_map = {s["id"]: s["name"] for s in speakers}
            segments_updated = 0
            
            for segment in transcription.get("segments", []):
                if segment.get("speaker") in speaker_map:
                    segment["speaker_name"] = speaker_map[segment["speaker"]]
                    segments_updated += 1
            
            # Save updated transcription
            await self.save_transcription(file_id, transcription)
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Updated {segments_updated} segments with speaker information for job {job_id}")
            return transcription
            
        except TranscriptionError:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            raise
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "update_speakers",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error updating speakers for job {job_id}: {str(e)}")
            raise TranscriptionError("Failed to update speakers", details=error_context)

    async def generate_text(
        self,
        transcription: TranscriptionData,
        include_foreign: bool = False
    ) -> str:
        """Generate plain text from transcription.
        
        Args:
            transcription: Transcription data to generate text from
            include_foreign: Whether to include foreign language segments
            
        Returns:
            Generated text
            
        Raises:
            TranscriptionError: If text generation fails
        """
        try:
            self._check_initialized()

            # Track operation start
            start_time = logging.time()
            
            # Validate transcription data
            if not isinstance(transcription, dict) or "segments" not in transcription:
                raise TranscriptionError("Invalid transcription data: missing segments")
            
            text = ""
            current_speaker = None
            segments_processed = 0
            
            for segment in transcription.get("segments", []):
                # Validate segment data
                if not isinstance(segment, dict) or "start" not in segment or "text" not in segment:
                    continue  # Skip invalid segments
                
                # Skip foreign language segments if not included
                if not include_foreign and segment.get("language") not in ["de", "en"]:
                    continue
                
                # Add speaker header if changed
                speaker = segment.get("speaker_name", segment.get("speaker", "Unknown"))
                if speaker != current_speaker:
                    if text:
                        text += "\n\n"
                    text += f"{speaker} ({self._format_time(segment['start'])}):\n"
                    current_speaker = speaker
                
                # Add segment text
                text += segment.get("text", "") + " "
                segments_processed += 1
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Generated text from {segments_processed} segments")
            return text.strip()
            
        except TranscriptionError:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            raise
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "generate_text",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "include_foreign": include_foreign
                }
            }
            log_error(f"Error generating text: {str(e)}")
            raise TranscriptionError("Failed to generate text", details=error_context)

    async def generate_srt(self, transcription: TranscriptionData) -> str:
        """Generate SRT subtitle file from transcription.
        
        Args:
            transcription: Transcription data to generate SRT from
            
        Returns:
            Generated SRT content
            
        Raises:
            TranscriptionError: If SRT generation fails
        """
        try:
            self._check_initialized()

            # Track operation start
            start_time = logging.time()
            
            # Validate transcription data
            if not isinstance(transcription, dict) or "segments" not in transcription:
                raise TranscriptionError("Invalid transcription data: missing segments")
            
            srt = ""
            segments_processed = 0
            
            for i, segment in enumerate(transcription.get("segments", []), 1):
                # Validate segment data
                if not isinstance(segment, dict) or "start" not in segment or "end" not in segment:
                    continue  # Skip invalid segments
                
                try:
                    # Add subtitle number
                    srt += f"{i}\n"
                    
                    # Add timestamp
                    start = self._format_srt_time(float(segment["start"]))
                    end = self._format_srt_time(float(segment["end"]))
                    srt += f"{start} --> {end}\n"
                    
                    # Add text with speaker
                    speaker = segment.get("speaker_name", segment.get("speaker", "Unknown"))
                    srt += f"{speaker}: {segment.get('text', '')}\n\n"
                    
                    segments_processed += 1
                except (ValueError, TypeError) as e:
                    log_warning(f"Invalid segment data at index {i}: {str(e)}")
                    continue
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Generated SRT from {segments_processed} segments")
            return srt.strip()
            
        except TranscriptionError:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            raise
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            error_context: ErrorContext = {
                "operation": "generate_srt",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error generating SRT: {str(e)}")
            raise TranscriptionError("Failed to generate SRT", details=error_context)

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to HH:MM:SS.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_srt_time(self, seconds: float) -> str:
        """Format time in seconds to SRT timestamp format (HH:MM:SS,mmm).
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted SRT timestamp
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"
