"""ZIP file handler service."""

import os
import zipfile
import asyncio
import tempfile
from typing import Dict, List
from ..utils.logging import log_info, log_error
from .interfaces import ZipHandlerInterface

class ZipHandlerService(ZipHandlerInterface):
    """Service for handling ZIP file uploads."""

    def __init__(self):
        """Initialize ZIP handler service."""
        self.initialized = False
        self.supported_audio_extensions = {'.mp3', '.wav', '.m4a', '.aac', '.mp4', '.mov'}

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            self.initialized = True
            log_info("ZIP handler service initialized")

        except Exception as e:
            log_error(f"Failed to initialize ZIP handler service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("ZIP handler service cleaned up")

        except Exception as e:
            log_error(f"Error during ZIP handler service cleanup: {str(e)}")
            raise

    async def process_zip_file(self, file_path: str, job_id: str) -> Dict:
        """Process a ZIP file for transcription."""
        try:
            # Create temporary directory for extraction
            with tempfile.TemporaryDirectory() as extract_dir:
                log_info(f"Extracting ZIP file {file_path} to {extract_dir}")
                
                # Extract ZIP contents
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Find audio/video files
                audio_files = []
                for root, _, files in os.walk(extract_dir):
                    for file in files:
                        ext = os.path.splitext(file.lower())[1]
                        if ext in self.supported_audio_extensions:
                            audio_files.append(os.path.join(root, file))
                
                if not audio_files:
                    raise ValueError("No audio/video files found in ZIP")
                
                # Sort files to ensure consistent order
                audio_files.sort()
                
                # Combine audio files if multiple
                if len(audio_files) > 1:
                    combined_file = await self.combine_audio_files(audio_files, job_id)
                    return {
                        "combined_file": combined_file,
                        "original_files": audio_files,
                        "is_combined": True
                    }
                else:
                    # Copy single file to a temporary location
                    temp_file = os.path.join(
                        tempfile.gettempdir(),
                        f"transcription_{job_id}{os.path.splitext(audio_files[0])[1]}"
                    )
                    with open(audio_files[0], 'rb') as src, open(temp_file, 'wb') as dst:
                        dst.write(src.read())
                    
                    return {
                        "combined_file": temp_file,
                        "original_files": audio_files,
                        "is_combined": False
                    }

        except Exception as e:
            log_error(f"Error processing ZIP file for job {job_id}: {str(e)}")
            raise

    async def combine_audio_files(self, audio_files: List[str], job_id: str) -> str:
        """Combine multiple audio files into one."""
        try:
            # Create temporary file for the list of files
            list_file = os.path.join(tempfile.gettempdir(), f"files_{job_id}.txt")
            
            # Create list of files for ffmpeg
            with open(list_file, 'w', encoding='utf-8') as f:
                for audio_file in audio_files:
                    f.write(f"file '{audio_file}'\n")
            
            # Output file path
            output_file = os.path.join(
                tempfile.gettempdir(),
                f"combined_{job_id}.wav"
            )
            
            # Use ffmpeg to concatenate files
            cmd = [
                "ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                output_file
            ]
            
            # Execute ffmpeg command
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise ValueError(f"Failed to combine audio files: {stderr.decode()}")
            
            # Clean up list file
            os.remove(list_file)
            
            return output_file

        except Exception as e:
            log_error(f"Error combining audio files for job {job_id}: {str(e)}")
            raise

    def is_supported_audio_file(self, filename: str) -> bool:
        """Check if a file has a supported audio/video extension."""
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.supported_audio_extensions

    def is_zip_file(self, filename: str) -> bool:
        """Check if a file is a ZIP file."""
        return filename.lower().endswith('.zip')
