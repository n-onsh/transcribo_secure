"""Transcription service."""

import logging
from typing import Dict, List, Optional
from ..utils.logging import log_info, log_error
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    track_transcription,
    track_transcription_error
)

class TranscriptionService:
    """Service for managing transcriptions."""

    def __init__(self, settings):
        """Initialize transcription service."""
        self.settings = settings
        self.initialized = False

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize settings
            self.storage_path = self.settings.get('storage_path', '/tmp/transcriptions')
            self.max_file_size = int(self.settings.get('max_file_size', 1073741824))  # 1GB

            self.initialized = True
            log_info("Transcription service initialized")

        except Exception as e:
            log_error(f"Failed to initialize transcription service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Transcription service cleaned up")

        except Exception as e:
            log_error(f"Error during transcription service cleanup: {str(e)}")
            raise

    async def get_transcription(self, file_id: str) -> Dict:
        """Get transcription data."""
        try:
            # Implementation would fetch from storage
            # For now return dummy data
            return {
                "segments": [
                    {
                        "start": 0,
                        "end": 5,
                        "text": "Hello world",
                        "speaker": "SPEAKER_01",
                        "language": "en"
                    }
                ]
            }
        except Exception as e:
            log_error(f"Error getting transcription for file {file_id}: {str(e)}")
            raise

    async def save_transcription(self, file_id: str, transcription: Dict):
        """Save transcription data."""
        try:
            # Implementation would save to storage
            log_info(f"Saved transcription for file {file_id}")
        except Exception as e:
            log_error(f"Error saving transcription for file {file_id}: {str(e)}")
            raise

    async def update_speakers(self, job_id: str, speakers: List[Dict]) -> Dict:
        """Update speaker information for a transcription."""
        try:
            # Get job
            job = await self.job_service.get_job(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            # Get transcription
            transcription = await self.get_transcription(job.file_id)
            
            # Update speaker information
            speaker_map = {s["id"]: s["name"] for s in speakers}
            for segment in transcription.get("segments", []):
                if segment.get("speaker") in speaker_map:
                    segment["speaker_name"] = speaker_map[segment["speaker"]]
            
            # Save updated transcription
            await self.save_transcription(job.file_id, transcription)
            
            return transcription
        except Exception as e:
            log_error(f"Error updating speakers for job {job_id}: {str(e)}")
            raise

    async def generate_text(self, transcription: Dict, include_foreign: bool = False) -> str:
        """Generate plain text from transcription."""
        try:
            text = ""
            current_speaker = None
            
            for segment in transcription.get("segments", []):
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
            
            return text.strip()
        except Exception as e:
            log_error(f"Error generating text: {str(e)}")
            raise

    async def generate_srt(self, transcription: Dict) -> str:
        """Generate SRT subtitle file from transcription."""
        try:
            srt = ""
            for i, segment in enumerate(transcription.get("segments", []), 1):
                # Add subtitle number
                srt += f"{i}\n"
                
                # Add timestamp
                start = self._format_srt_time(segment["start"])
                end = self._format_srt_time(segment["end"])
                srt += f"{start} --> {end}\n"
                
                # Add text with speaker
                speaker = segment.get("speaker_name", segment.get("speaker", "Unknown"))
                srt += f"{speaker}: {segment.get('text', '')}\n\n"
            
            return srt.strip()
        except Exception as e:
            log_error(f"Error generating SRT: {str(e)}")
            raise

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
