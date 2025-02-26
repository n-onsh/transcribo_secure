"""Transcription service."""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import StorageError, TranscriptionError
from .storage import StorageService
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    track_transcription,
    track_transcription_error
)

class TranscriptionService:
    """Service for managing transcriptions."""

    def __init__(
        self,
        settings,
        storage_service: Optional[StorageService] = None,
        job_service = None
    ):
        """Initialize transcription service."""
        self.settings = settings
        self.initialized = False
        self.storage = storage_service
        self.job_service = job_service

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Transcription service cleaned up")

        except Exception as e:
            log_error(f"Error during transcription service cleanup: {str(e)}")
            raise

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

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

            self.initialized = True
            log_info("Transcription service initialized")

        except Exception as e:
            log_error(f"Failed to initialize transcription service: {str(e)}")
            raise

    async def get_transcription(self, file_id: str) -> Dict:
        """Get transcription data."""
        if not self.initialized:
            raise TranscriptionError("Service not initialized")
            
        try:
            # Track operation start
            start_time = logging.time()
            
            # Get transcription file path
            file_path = self._get_transcription_path(file_id)
            
            # Read transcription data
            data = await self.storage.get_file(str(file_path))
            if not data:
                raise TranscriptionError(f"Transcription not found for file {file_id}")
            
            # Parse JSON data
            try:
                transcription = json.loads(data.decode('utf-8'))
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
            log_error(f"Storage error getting transcription for file {file_id}: {str(e)}")
            raise TranscriptionError(f"Failed to get transcription: {str(e)}")
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            log_error(f"Error getting transcription for file {file_id}: {str(e)}")
            raise TranscriptionError(f"Failed to get transcription: {str(e)}")

    async def save_transcription(self, file_id: str, transcription: Dict):
        """Save transcription data."""
        if not self.initialized:
            raise TranscriptionError("Service not initialized")
            
        try:
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
            await self.storage.store_file(str(file_path), data)
            
            # Track duration
            duration = logging.time() - start_time
            TRANSCRIPTION_DURATION.observe(duration)
            track_transcription(duration)
            
            log_info(f"Saved transcription for file {file_id}")
            
        except StorageError as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            log_error(f"Storage error saving transcription for file {file_id}: {str(e)}")
            raise TranscriptionError(f"Failed to save transcription: {str(e)}")
        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            log_error(f"Error saving transcription for file {file_id}: {str(e)}")
            raise TranscriptionError(f"Failed to save transcription: {str(e)}")

    def _get_transcription_path(self, file_id: str) -> Path:
        """Get path for transcription file."""
        # Use first 2 characters of file ID for subdirectory to avoid too many files in one directory
        subdir = file_id[:2]
        return self.storage_path / subdir / f"{file_id}.json"

    async def update_speakers(self, job_id: str, speakers: List[Dict]) -> Dict:
        """Update speaker information for a transcription."""
        if not self.initialized:
            raise TranscriptionError("Service not initialized")
            
        try:
            # Track operation start
            start_time = logging.time()
            
            # Validate speakers data
            if not all(s.get("id") and s.get("name") for s in speakers):
                raise TranscriptionError("Invalid speaker data: missing id or name")
            
            # Get job
            try:
                job = await self.job_service.get_job(job_id)
                if not job:
                    raise TranscriptionError(f"Job {job_id} not found")
            except Exception as e:
                raise TranscriptionError(f"Failed to get job: {str(e)}")
            
            # Get transcription
            transcription = await self.get_transcription(job.file_id)
            
            # Update speaker information
            speaker_map = {s["id"]: s["name"] for s in speakers}
            segments_updated = 0
            
            for segment in transcription.get("segments", []):
                if segment.get("speaker") in speaker_map:
                    segment["speaker_name"] = speaker_map[segment["speaker"]]
                    segments_updated += 1
            
            # Save updated transcription
            await self.save_transcription(job.file_id, transcription)
            
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
            log_error(f"Error updating speakers for job {job_id}: {str(e)}")
            raise TranscriptionError(f"Failed to update speakers: {str(e)}")

    async def generate_text(self, transcription: Dict, include_foreign: bool = False) -> str:
        """Generate plain text from transcription."""
        if not self.initialized:
            raise TranscriptionError("Service not initialized")
            
        try:
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
            log_error(f"Error generating text: {str(e)}")
            raise TranscriptionError(f"Failed to generate text: {str(e)}")

    async def generate_srt(self, transcription: Dict) -> str:
        """Generate SRT subtitle file from transcription."""
        if not self.initialized:
            raise TranscriptionError("Service not initialized")
            
        try:
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
            log_error(f"Error generating SRT: {str(e)}")
            raise TranscriptionError(f"Failed to generate SRT: {str(e)}")

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds to HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_srt_time(self, seconds: float) -> str:
        """Format time in seconds to SRT timestamp format (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds_int = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds_int:02d},{milliseconds:03d}"
