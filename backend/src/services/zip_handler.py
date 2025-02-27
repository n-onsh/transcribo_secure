"""ZIP file handler service."""

import os
import uuid
import zipfile
import asyncio
import tempfile
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Set, cast
from datetime import datetime
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import ZipError, TranscriboError, StorageError
from ..types import (
    ServiceConfig,
    ErrorContext,
    ZipProcessingResult,
    ZipValidationResult,
    ZipFileInfo,
    ZipProgressCallback,
    ZipConfig,
    JobID,
    FileID,
    ProgressStage
)
from .base import BaseService
from .storage import StorageService
from .encryption import EncryptionService
from ..utils.metrics import (
    ZIP_PROCESSING_TIME,
    ZIP_EXTRACTION_ERRORS,
    ZIP_FILE_COUNT,
    ZIP_TOTAL_SIZE,
    track_zip_processing,
    track_zip_error
)
from ..services.provider import service_provider

class ZipHandlerService(BaseService):
    """Service for handling ZIP file uploads."""

    def __init__(
        self,
        settings: ServiceConfig,
        storage_service: StorageService,
        encryption_service: EncryptionService
    ) -> None:
        """Initialize ZIP handler service.
        
        Args:
            settings: Service configuration
            storage_service: Storage service for file operations
            encryption_service: Encryption service for file encryption
        """
        super().__init__(settings)
        
        # Required services
        self.storage_service = storage_service
        self.encryption_service = encryption_service
        
        # Configuration
        self.supported_audio_extensions: Set[str] = set(
            settings.get('supported_audio_extensions', 
            ['.mp3', '.wav', '.m4a', '.aac', '.mp4', '.mov'])
        )
        self.max_zip_size: int = int(settings.get('max_zip_size', 12 * 1024 * 1024 * 1024))  # Default 12GB
        self.ffmpeg_path: str = settings.get('ffmpeg_path', 'ffmpeg')
        
        # Runtime state
        self.progress_callbacks: Dict[JobID, ZipProgressCallback] = {}
        self.temp_dirs: Set[str] = set()
        self.temp_files: Set[str] = set()
        
        log_info("ZIP handler service initialized")

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        # No initialization needed since services are injected
        pass

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
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
            
            log_info("ZIP handler service cleaned up")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_zip_handler",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during ZIP handler service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up ZIP handler service",
                details=error_context
            )

    @asynccontextmanager
    async def _extraction_context(self, job_id: JobID) -> AsyncGenerator[str, None]:
        """Context manager for ZIP extraction with memory management.
        
        Args:
            job_id: Job ID for tracking
            
        Yields:
            Path to extraction directory
        """
        extract_dir = None
        try:
            # Create temporary directory
            extract_dir = tempfile.mkdtemp()
            self.temp_dirs.add(extract_dir)
            yield extract_dir
        finally:
            if extract_dir:
                await self.cleanup_extract_dir(extract_dir)

    async def _extract_with_progress(
        self,
        zip_ref: zipfile.ZipFile,
        extract_dir: str,
        job_id: JobID,
        chunk_size: int = 8192
    ) -> None:
        """Extract ZIP contents with progress tracking and memory optimization.
        
        Args:
            zip_ref: ZIP file reference
            extract_dir: Directory to extract to
            job_id: Job ID for tracking
            chunk_size: Size of chunks to read
        """
        total_size = sum(info.file_size for info in zip_ref.filelist)
        ZIP_TOTAL_SIZE.observe(total_size)
        
        extracted_size = 0
        for item in zip_ref.filelist:
            # Extract file in chunks
            source = zip_ref.open(item)
            target_path = os.path.join(extract_dir, item.filename)
            
            # Create directories if needed
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, 'wb') as target:
                while True:
                    chunk = source.read(chunk_size)
                    if not chunk:
                        break
                    target.write(chunk)
                    extracted_size += len(chunk)
                    
                    # Update progress
                    progress = (extracted_size / total_size) * 100
                    await self.update_progress(
                        job_id,
                        ProgressStage.EXTRACTING,
                        progress
                    )
            source.close()

    async def process_zip_file(
        self,
        file_path: str,
        job_id: JobID,
        progress_callback: Optional[ZipProgressCallback] = None,
        encrypt: bool = True
    ) -> ZipProcessingResult:
        """Process a ZIP file for transcription.
        
        Args:
            file_path: Path to ZIP file
            job_id: Job ID for tracking
            progress_callback: Optional callback for progress updates
            encrypt: Whether to encrypt extracted files
            
        Returns:
            ZIP processing result
            
        Raises:
            ZipError: If ZIP processing fails
        """
        start_time = asyncio.get_event_loop().time()

        try:
            self._check_initialized()

            # Validate ZIP file
            validation_result = await self.validate_zip_file(file_path)
            if not validation_result.is_valid:
                raise ZipError(
                    "Invalid ZIP file",
                    details={"errors": validation_result.errors}
                )
            
            # Store progress callback
            if progress_callback:
                self.progress_callbacks[job_id] = progress_callback
            
            # Process ZIP file with memory management
            async with self._extraction_context(job_id) as extract_dir:
                log_info(f"Extracting ZIP file {file_path} to {extract_dir}")
                
                # Update progress
                await self.update_progress(job_id, ProgressStage.EXTRACTING, 0)
                
                # Extract files with progress tracking
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    await self._extract_with_progress(zip_ref, extract_dir, job_id)
            
                # Find and process audio files
                audio_files = await self._find_audio_files(extract_dir)
                
                ZIP_FILE_COUNT.observe(len(audio_files))
                
                if not audio_files:
                    raise ZipError("No audio/video files found in ZIP")
                
                # Sort files to ensure consistent order
                audio_files.sort()
                
                # Update progress
                await self.update_progress(job_id, ProgressStage.PROCESSING, 0)
                
                # Process files with retries
                processed_files = await self._process_audio_files(
                    audio_files,
                    job_id,
                    encrypt
                )
            
                # Combine audio files if multiple
                combined_result = None
                combined_id = None
                if len(audio_files) > 1:
                    combined_result = await self._combine_and_store_files(
                        audio_files,
                        processed_files,
                        job_id,
                        encrypt
                    )
                    combined_id = combined_result['file_id']
            
                # Track processing time
                processing_time = asyncio.get_event_loop().time() - start_time
                ZIP_PROCESSING_TIME.observe(processing_time)
                track_zip_processing(processing_time)
                
                # Update progress
                await self.update_progress(job_id, ProgressStage.COMPLETED, 100)
                
                # Return result
                if combined_result:
                    return ZipProcessingResult(
                        combined_file=combined_result['path'],
                        combined_file_id=str(combined_id),
                        original_files=processed_files,
                        is_combined=True,
                        extract_dir=extract_dir
                    )
                else:
                    return ZipProcessingResult(
                        combined_file=processed_files[0]['path'],
                        combined_file_id=processed_files[0]['file_id'],
                        original_files=processed_files,
                        is_combined=False,
                        extract_dir=extract_dir
                    )

        except Exception as e:
            ZIP_EXTRACTION_ERRORS.inc()
            track_zip_error()
            error_context: ErrorContext = {
                "operation": "process_zip_file",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_path": file_path
                }
            }
            log_error(f"Error processing ZIP file for job {job_id}: {str(e)}")
            
            # Update progress on error
            await self.update_progress(job_id, ProgressStage.FAILED, 0)
            
            raise ZipError("Failed to process ZIP file", details=error_context)

    async def validate_zip_file(self, file_path: str) -> ZipValidationResult:
        """Validate ZIP file before processing.
        
        Args:
            file_path: Path to ZIP file to validate
            
        Returns:
            Validation result
            
        Raises:
            ZipError: If validation fails
        """
        errors = []
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.max_zip_size:
                errors.append(
                    f"ZIP file too large. Maximum size is {self.max_zip_size / (1024*1024*1024):.1f}GB"
                )
            
            audio_files = []
            total_size = 0
            file_count = 0
            
            # Verify ZIP integrity
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                # Check for encryption
                if any(info.flag_bits & 0x1 for info in zip_ref.filelist):
                    errors.append("Encrypted ZIP files are not supported")
                
                # Test ZIP integrity
                error_list = zip_ref.testzip()
                if error_list:
                    errors.append(f"Corrupt ZIP file, first bad file: {error_list}")
                
                # Check total uncompressed size
                total_size = sum(info.file_size for info in zip_ref.filelist)
                if total_size > self.max_zip_size * 2:  # Allow for some compression
                    errors.append("Uncompressed content too large")
                
                # Count files and find audio files
                file_count = len(zip_ref.filelist)
                for info in zip_ref.filelist:
                    ext = os.path.splitext(info.filename.lower())[1]
                    if ext in self.supported_audio_extensions:
                        audio_files.append(info.filename)
                
                if not audio_files:
                    errors.append("No audio/video files found in ZIP")
            
            return ZipValidationResult(
                is_valid=len(errors) == 0,
                file_count=file_count,
                total_size=total_size,
                audio_files=audio_files,
                errors=errors
            )
            
        except zipfile.BadZipFile as e:
            return ZipValidationResult(
                is_valid=False,
                file_count=0,
                total_size=0,
                audio_files=[],
                errors=[f"Invalid ZIP file: {str(e)}"]
            )
        except Exception as e:
            return ZipValidationResult(
                is_valid=False,
                file_count=0,
                total_size=0,
                audio_files=[],
                errors=[f"Validation failed: {str(e)}"]
            )

    async def update_progress(
        self,
        job_id: JobID,
        stage: ProgressStage,
        progress: float
    ) -> None:
        """Update progress through callback if registered.
        
        Args:
            job_id: Job ID for tracking
            stage: Current processing stage
            progress: Progress percentage (0-100)
        """
        if job_id in self.progress_callbacks:
            try:
                await self.progress_callbacks[job_id](str(stage), progress)
            except Exception as e:
                log_warning(f"Failed to update progress for job {job_id}: {str(e)}")

    async def cleanup_extract_dir(self, extract_dir: str) -> None:
        """Clean up extraction directory.
        
        Args:
            extract_dir: Directory to clean up
        """
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

    async def combine_audio_files(
        self,
        audio_files: List[str],
        job_id: JobID
    ) -> str:
        """Combine multiple audio files into one.
        
        Args:
            audio_files: List of audio file paths to combine
            job_id: Job ID for tracking
            
        Returns:
            Path to combined audio file
            
        Raises:
            ZipError: If audio file combination fails
        """
        list_file = None
        output_file = None
        
        try:
            # Validate audio files
            for file_path in audio_files:
                if not await self.validate_audio_file(file_path):
                    raise ZipError(f"Invalid or unsupported audio file: {file_path}")
            
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
                    raise ZipError(f"ffmpeg not found at {self.ffmpeg_path}")
                elif "Invalid data found when processing input" in error_msg:
                    raise ZipError("Invalid or corrupted audio file detected")
                else:
                    raise ZipError(f"Failed to combine audio files: {error_msg}")
            
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
            
            error_context: ErrorContext = {
                "operation": "combine_audio_files",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_count": len(audio_files)
                }
            }
            log_error(f"Error combining audio files for job {job_id}: {str(e)}")
            raise ZipError("Failed to combine audio files", details=error_context)

    async def validate_audio_file(self, file_path: str) -> bool:
        """Validate audio file format using ffprobe.
        
        Args:
            file_path: Path to audio file to validate
            
        Returns:
            True if file is valid, False otherwise
        """
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

    async def get_mime_type(self, file_path: str) -> str:
        """Get MIME type for a file.
        
        Args:
            file_path: Path to file
            
        Returns:
            MIME type string
        """
        mime_type, _ = mimetypes.guess_type(file_path)
        return mime_type or 'application/octet-stream'

    def is_supported_audio_file(self, filename: str) -> bool:
        """Check if a file has a supported audio/video extension.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if file extension is supported, False otherwise
        """
        ext = os.path.splitext(filename.lower())[1]
        return ext in self.supported_audio_extensions

    def is_zip_file(self, filename: str) -> bool:
        """Check if a file is a ZIP file.
        
        Args:
            filename: Filename to check
            
        Returns:
            True if file is a ZIP file, False otherwise
        """
        return filename.lower().endswith('.zip')

    async def _find_audio_files(self, extract_dir: str) -> List[str]:
        """Find audio files in extracted directory.
        
        Args:
            extract_dir: Directory to search in
            
        Returns:
            List of audio file paths
        """
        audio_files = []
        for root, _, files in os.walk(extract_dir):
            for file in files:
                ext = os.path.splitext(file.lower())[1]
                if ext in self.supported_audio_extensions:
                    audio_files.append(os.path.join(root, file))
        return audio_files

    async def _process_audio_files(
        self,
        audio_files: List[str],
        job_id: JobID,
        encrypt: bool
    ) -> List[Dict]:
        """Process audio files with retries.
        
        Args:
            audio_files: List of audio file paths
            job_id: Job ID for tracking
            encrypt: Whether to encrypt files
            
        Returns:
            List of processed file information
            
        Raises:
            ZipError: If processing fails
        """
        processed_files = []
        max_retries = 3
        retry_delay = 1.0

        for i, file_path in enumerate(audio_files):
            for attempt in range(max_retries):
                try:
                    # Get file info
                    file_size = os.path.getsize(file_path)
                    mime_type = await self.get_mime_type(file_path)
                    
                    # Generate file ID
                    file_id = uuid.uuid4()
                    
                    # Store file with encryption if requested
                    with open(file_path, 'rb') as f:
                        result = await self.storage_service.store_file(
                            file_id=file_id,
                            file=f,
                            metadata={
                                'original_filename': os.path.basename(file_path),
                                'job_id': job_id,
                                'content_type': mime_type,
                                'size': file_size
                            },
                            encrypt=encrypt
                        )
                        processed_files.append({
                            'file_id': str(file_id),
                            'path': result['path'],
                            'size': result['size'],
                            'encrypted': result['encrypted'],
                            'original_path': file_path,
                            'content_type': mime_type
                        })
                        break
                except StorageError as e:
                    if attempt == max_retries - 1:
                        raise ZipError(f"Failed to store file after {max_retries} attempts: {str(e)}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
            
            # Update progress
            await self.update_progress(
                job_id,
                ProgressStage.PROCESSING,
                (i + 1) / len(audio_files) * 100
            )
        
        return processed_files

    async def _combine_and_store_files(
        self,
        audio_files: List[str],
        processed_files: List[Dict],
        job_id: JobID,
        encrypt: bool
    ) -> Dict:
        """Combine and store audio files.
        
        Args:
            audio_files: List of audio file paths
            processed_files: List of processed file information
            job_id: Job ID for tracking
            encrypt: Whether to encrypt files
            
        Returns:
            Combined file information
            
        Raises:
            ZipError: If combining fails
        """
        try:
            # Combine audio files
            combined_file = await self.combine_audio_files(audio_files, job_id)
            
            # Store combined file
            combined_id = uuid.uuid4()
            with open(combined_file, 'rb') as f:
                try:
                    result = await self.storage_service.store_file(
                        file_id=combined_id,
                        file=f,
                        metadata={
                            'original_filename': f"combined_{job_id}.wav",
                            'job_id': job_id,
                            'content_type': 'audio/wav',
                            'is_combined': True,
                            'source_files': [f['file_id'] for f in processed_files]
                        },
                        encrypt=encrypt
                    )
                    result['file_id'] = str(combined_id)
                    return result
                except StorageError as e:
                    raise ZipError(f"Failed to store combined file: {str(e)}")
                finally:
                    # Clean up combined file
                    if os.path.exists(combined_file):
                        os.remove(combined_file)
                        if combined_file in self.temp_files:
                            self.temp_files.remove(combined_file)
        except Exception as e:
            raise ZipError(f"Failed to combine and store files: {str(e)}")
