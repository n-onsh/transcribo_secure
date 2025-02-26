"""ZIP file handler service."""

import os
import zipfile
import asyncio
import tempfile
from typing import Dict, List, Optional, Tuple
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    ZIP_PROCESSING_TIME,
    ZIP_EXTRACTION_ERRORS,
    ZIP_FILE_COUNT,
    ZIP_TOTAL_SIZE,
    track_zip_processing,
    track_zip_error
)
from .interfaces import ZipHandlerInterface

class ZipHandlerService(ZipHandlerInterface):
    """Service for handling ZIP file uploads."""

    def __init__(self, settings: Dict):
        """Initialize ZIP handler service."""
        self.initialized = False
        self.settings = settings
        self.supported_audio_extensions = set(
            settings.get('supported_audio_extensions', 
            ['.mp3', '.wav', '.m4a', '.aac', '.mp4', '.mov'])
        )
        self.progress_callbacks = {}
        self.temp_dirs = set()
        self.temp_files = set()
        self.max_zip_size = int(settings.get('max_zip_size', 12 * 1024 * 1024 * 1024))  # Default 12GB
        self.ffmpeg_path = settings.get('ffmpeg_path', 'ffmpeg')

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
            # Clean up all temporary directories
            for dir_path in list(self.temp_dirs):
                await self.cleanup_extract_dir(dir_path)
            
            # Clean up all temporary files
            for file_path in list(self.temp_files):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.temp_files.remove(file_path)
                except Exception as e:
                    log_warning(f"Failed to remove temporary file {file_path}: {str(e)}")
            
            self.initialized = False
            log_info("ZIP handler service cleaned up")

        except Exception as e:
            log_error(f"Error during ZIP handler service cleanup: {str(e)}")
            raise

    async def process_zip_file(self, file_path: str, job_id: str, progress_callback=None) -> Dict:
        """Process a ZIP file for transcription."""
        start_time = asyncio.get_event_loop().time()
        extract_dir = None

        try:
            # Validate ZIP file
            await self.validate_zip_file(file_path)
            
            # Create temporary directory for extraction
            extract_dir = tempfile.mkdtemp()
            self.temp_dirs.add(extract_dir)
            
            # Store progress callback
            if progress_callback:
                self.progress_callbacks[job_id] = progress_callback
            
            log_info(f"Extracting ZIP file {file_path} to {extract_dir}")
            
            # Get total size and file count
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                total_size = sum(info.file_size for info in zip_ref.filelist)
                ZIP_TOTAL_SIZE.observe(total_size)
                
                # Extract with progress tracking
                extracted_size = 0
                for item in zip_ref.filelist:
                    zip_ref.extract(item, extract_dir)
                    extracted_size += item.file_size
                    await self.update_progress(job_id, "extracting", extracted_size / total_size * 100)
                
            # Find audio/video files
            audio_files = []
            for root, _, files in os.walk(extract_dir):
                for file in files:
                    ext = os.path.splitext(file.lower())[1]
                    if ext in self.supported_audio_extensions:
                        audio_files.append(os.path.join(root, file))
            
            ZIP_FILE_COUNT.observe(len(audio_files))
                
            if not audio_files:
                raise ValueError("No audio/video files found in ZIP")
            
            # Sort files to ensure consistent order
            audio_files.sort()
            
            # Update progress
            await self.update_progress(job_id, "processing", 0)
            
            # Combine audio files if multiple
            if len(audio_files) > 1:
                combined_file = await self.combine_audio_files(audio_files, job_id)
                processing_time = asyncio.get_event_loop().time() - start_time
                ZIP_PROCESSING_TIME.observe(processing_time)
                track_zip_processing(processing_time)
                
                return {
                    "combined_file": combined_file,
                    "original_files": audio_files,
                    "is_combined": True,
                    "extract_dir": extract_dir
                }
            else:
                # Copy single file to a temporary location
                temp_file = os.path.join(
                    tempfile.gettempdir(),
                    f"transcription_{job_id}{os.path.splitext(audio_files[0])[1]}"
                )
                with open(audio_files[0], 'rb') as src, open(temp_file, 'wb') as dst:
                    dst.write(src.read())
                
                processing_time = asyncio.get_event_loop().time() - start_time
                ZIP_PROCESSING_TIME.observe(processing_time)
                track_zip_processing(processing_time)
                
                return {
                    "combined_file": temp_file,
                    "original_files": audio_files,
                    "is_combined": False,
                    "extract_dir": extract_dir
                }

        except Exception as e:
            ZIP_EXTRACTION_ERRORS.inc()
            track_zip_error()
            log_error(f"Error processing ZIP file for job {job_id}: {str(e)}")
            if extract_dir:
                await self.cleanup_extract_dir(extract_dir)
            raise

    async def validate_zip_file(self, file_path: str) -> None:
        """Validate ZIP file before processing."""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_zip_size:
                raise ValueError(f"ZIP file too large. Maximum size is {self.max_zip_size / (1024*1024*1024):.1f}GB")
            
            # Verify ZIP integrity
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Check for encryption
                if any(info.flag_bits & 0x1 for info in zip_ref.filelist):
                    raise ValueError("Encrypted ZIP files are not supported")
                
                # Test ZIP integrity
                error_list = zip_ref.testzip()
                if error_list:
                    raise ValueError(f"Corrupt ZIP file, first bad file: {error_list}")
                
                # Check total uncompressed size
                total_size = sum(info.file_size for info in zip_ref.filelist)
                if total_size > self.max_zip_size * 2:  # Allow for some compression
                    raise ValueError("Uncompressed content too large")
                
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid ZIP file: {str(e)}")
        except Exception as e:
            raise ValueError(f"ZIP validation failed: {str(e)}")

    async def update_progress(self, job_id: str, stage: str, progress: float) -> None:
        """Update progress through callback if registered."""
        if job_id in self.progress_callbacks:
            try:
                await self.progress_callbacks[job_id](stage, progress)
            except Exception as e:
                log_warning(f"Failed to update progress for job {job_id}: {str(e)}")

    async def cleanup_extract_dir(self, extract_dir: str) -> None:
        """Clean up extraction directory."""
        try:
            if extract_dir in self.temp_dirs:
                self.temp_dirs.remove(extract_dir)
            if os.path.exists(extract_dir):
                for root, dirs, files in os.walk(extract_dir, topdown=False):
                    for name in files:
                        try:
                            os.remove(os.path.join(root, name))
                        except Exception as e:
                            log_warning(f"Failed to remove file {name}: {str(e)}")
                    for name in dirs:
                        try:
                            os.rmdir(os.path.join(root, name))
                        except Exception as e:
                            log_warning(f"Failed to remove directory {name}: {str(e)}")
                os.rmdir(extract_dir)
        except Exception as e:
            log_warning(f"Failed to clean up directory {extract_dir}: {str(e)}")

    async def combine_audio_files(self, audio_files: List[str], job_id: str) -> str:
        """Combine multiple audio files into one."""
        list_file = None
        output_file = None
        
        try:
            # Validate audio files
            for file_path in audio_files:
                if not await self.validate_audio_file(file_path):
                    raise ValueError(f"Invalid or unsupported audio file: {file_path}")
            
            # Create temporary file for the list of files
            list_file = os.path.join(tempfile.gettempdir(), f"files_{job_id}.txt")
            self.temp_files.add(list_file)
            
            # Create list of files for ffmpeg
            with open(list_file, 'w', encoding='utf-8') as f:
                for audio_file in audio_files:
                    f.write(f"file '{audio_file}'\n")
            
            # Output file path
            output_file = os.path.join(
                tempfile.gettempdir(),
                f"combined_{job_id}.wav"
            )
            self.temp_files.add(output_file)
            
            # Use ffmpeg to concatenate files
            cmd = [
                self.ffmpeg_path,
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
                error_msg = stderr.decode()
                if "No such file or directory" in error_msg:
                    raise ValueError(f"ffmpeg not found at {self.ffmpeg_path}")
                elif "Invalid data found when processing input" in error_msg:
                    raise ValueError("Invalid or corrupted audio file detected")
                else:
                    raise ValueError(f"Failed to combine audio files: {error_msg}")
            
            # Clean up list file
            if list_file and os.path.exists(list_file):
                os.remove(list_file)
                self.temp_files.remove(list_file)
            
            return output_file

        except Exception as e:
            # Clean up temporary files on error
            if list_file and os.path.exists(list_file):
                os.remove(list_file)
                self.temp_files.remove(list_file)
            if output_file and os.path.exists(output_file):
                os.remove(output_file)
                self.temp_files.remove(output_file)
            
            log_error(f"Error combining audio files for job {job_id}: {str(e)}")
            raise

    async def validate_audio_file(self, file_path: str) -> bool:
        """Validate audio file format using ffprobe."""
        try:
            # Use ffprobe to check file format
            cmd = [
                self.ffmpeg_path.replace('ffmpeg', 'ffprobe'),
                "-v", "error",
                "-select_streams", "a:0",  # Select first audio stream
                "-show_entries", "stream=codec_name",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                log_warning(f"Failed to validate audio file {file_path}: {stderr.decode()}")
                return False
            
            # Check if ffprobe found an audio stream
            codec = stdout.decode().strip()
            return bool(codec)
            
        except Exception as e:
            log_warning(f"Error validating audio file {file_path}: {str(e)}")
            return False

    def is_supported_audio_file(self, filename: str) -> bool:
        """Check if a file has a supported audio/video extension."""
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.supported_audio_extensions

    def is_zip_file(self, filename: str) -> bool:
        """Check if a file is a ZIP file."""
        return filename.lower().endswith('.zip')
