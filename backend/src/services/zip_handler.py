"""ZIP file handling service."""

import asyncio
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Set, Tuple
from uuid import UUID

from opentelemetry import trace, logs
from opentelemetry.logs import Severity

from ..models.file import File
from ..models.job import Job, JobStatus
from ..services.storage import StorageService
from ..services.job_manager import JobManager
from ..utils.metrics import (
    ZIP_EXTRACTION_TIME,
    ZIP_FILE_COUNT,
    ZIP_TOTAL_SIZE,
    ZIP_ERROR_COUNT,
    track_time,
    track_errors,
    update_gauge
)

logger = logs.get_logger(__name__)
tracer = trace.get_tracer(__name__)

class ZipHandler:
    """Handles ZIP file extraction and processing."""
    
    def __init__(
        self,
        storage: StorageService,
        job_manager: JobManager,
        max_file_size: int = 1024 * 1024 * 1024,  # 1GB
        max_files: int = 100,
        allowed_extensions: Set[str] = {'mp3', 'wav', 'm4a'},
        chunk_size: int = 8192,  # 8KB
        extraction_timeout: int = 3600  # 1 hour
    ):
        self.storage = storage
        self.job_manager = job_manager
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.allowed_extensions = allowed_extensions
        self.chunk_size = chunk_size
        self.extraction_timeout = extraction_timeout
        
        # Track active extractions
        self.active_extractions: Dict[UUID, asyncio.Task] = {}

    @track_time("zip_validation_duration", {"operation": "validate"})
    @track_errors("zip_validation_errors", {"operation": "validate"})
    async def validate_zip(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate ZIP file before extraction."""
        try:
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Check for encryption
                if any(info.flag_bits & 0x1 for info in zip_file.filelist):
                    return False, "Encrypted ZIP files are not supported"
                
                # Check file count
                if len(zip_file.filelist) > self.max_files:
                    return False, f"ZIP contains too many files (max {self.max_files})"
                
                # Check total size
                total_size = sum(info.file_size for info in zip_file.filelist)
                if total_size > self.max_file_size:
                    return False, f"ZIP contents too large (max {self.max_file_size} bytes)"
                
                # Check extensions
                invalid_files = [
                    info.filename for info in zip_file.filelist
                    if Path(info.filename).suffix[1:].lower() not in self.allowed_extensions
                ]
                if invalid_files:
                    return False, f"Invalid file types: {', '.join(invalid_files)}"
                
                # Test integrity
                if zip_file.testzip() is not None:
                    return False, "ZIP file is corrupted"
                
                return True, None
                
        except zipfile.BadZipFile:
            return False, "Invalid ZIP file format"
        except Exception as e:
            logger.emit(
                "ZIP validation error",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            return False, f"Validation error: {str(e)}"

    @track_time("zip_extraction_duration", {"operation": "extract"})
    @track_errors("zip_extraction_errors", {"operation": "extract"})
    async def extract_zip(
        self,
        file_id: UUID,
        owner_id: UUID,
        file_path: str,
        language: Optional[str] = None
    ) -> AsyncGenerator[Tuple[str, float], None]:
        """Extract and process ZIP contents."""
        try:
            # Start extraction task
            task = asyncio.create_task(
                self._extract_files(file_id, owner_id, file_path, language)
            )
            self.active_extractions[file_id] = task
            
            # Track metrics
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                ZIP_FILE_COUNT.inc(len(zip_file.filelist))
                ZIP_TOTAL_SIZE.inc(
                    sum(info.file_size for info in zip_file.filelist)
                )
            
            # Process files with timeout
            start_time = datetime.utcnow()
            async for filename, progress in asyncio.wait_for(
                task, timeout=self.extraction_timeout
            ):
                yield filename, progress
                
            # Record extraction time
            extraction_time = (datetime.utcnow() - start_time).total_seconds()
            ZIP_EXTRACTION_TIME.observe(extraction_time)
            
        except asyncio.TimeoutError:
            ZIP_ERROR_COUNT.inc()
            logger.emit(
                "ZIP extraction timeout",
                severity=Severity.ERROR,
                attributes={"file_id": str(file_id)}
            )
            raise
            
        except Exception as e:
            ZIP_ERROR_COUNT.inc()
            logger.emit(
                "ZIP extraction error",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_id": str(file_id)
                }
            )
            raise
            
        finally:
            # Cleanup
            self.active_extractions.pop(file_id, None)
            try:
                os.remove(file_path)
            except Exception as e:
                logger.emit(
                    "Failed to remove ZIP file",
                    severity=Severity.WARNING,
                    attributes={
                        "error": str(e),
                        "file_id": str(file_id)
                    }
                )

    async def _extract_files(
        self,
        file_id: UUID,
        owner_id: UUID,
        file_path: str,
        language: Optional[str]
    ) -> AsyncGenerator[Tuple[str, float], None]:
        """Extract files from ZIP and create jobs."""
        with zipfile.ZipFile(file_path, 'r') as zip_file:
            total_files = len(zip_file.filelist)
            processed_files = 0
            
            for info in zip_file.filelist:
                # Skip directories
                if info.is_dir():
                    continue
                
                try:
                    # Extract file
                    with zip_file.open(info) as source, \
                         open(f"/tmp/{info.filename}", 'wb') as target:
                        while chunk := source.read(self.chunk_size):
                            target.write(chunk)
                    
                    # Upload to storage
                    file = File(
                        id=UUID(int=file_id.int + processed_files + 1),
                        owner_id=owner_id,
                        name=info.filename,
                        size=info.file_size,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    await self.storage.upload_file(
                        file=file,
                        file_path=f"/tmp/{info.filename}"
                    )
                    
                    # Create job
                    job = Job(
                        id=UUID(int=file_id.int + processed_files + 1),
                        owner_id=owner_id,
                        file_name=info.filename,
                        file_size=info.file_size,
                        status=JobStatus.PENDING,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    await self.job_manager.create_job(
                        job=job,
                        language=language
                    )
                    
                    # Update progress
                    processed_files += 1
                    progress = processed_files / total_files * 100
                    yield info.filename, progress
                    
                except Exception as e:
                    logger.emit(
                        "Failed to process ZIP file",
                        severity=Severity.ERROR,
                        attributes={
                            "error": str(e),
                            "filename": info.filename,
                            "file_id": str(file_id)
                        }
                    )
                    raise
                    
                finally:
                    # Cleanup temp file
                    try:
                        os.remove(f"/tmp/{info.filename}")
                    except Exception as e:
                        logger.emit(
                            "Failed to remove temp file",
                            severity=Severity.WARNING,
                            attributes={
                                "error": str(e),
                                "filename": info.filename
                            }
                        )

    async def cancel_extraction(self, file_id: UUID) -> None:
        """Cancel ongoing ZIP extraction."""
        if task := self.active_extractions.get(file_id):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            logger.emit(
                "ZIP extraction cancelled",
                severity=Severity.INFO,
                attributes={"file_id": str(file_id)}
            )

    async def get_extraction_progress(self, file_id: UUID) -> Optional[float]:
        """Get progress of ongoing extraction."""
        if task := self.active_extractions.get(file_id):
            if not task.done():
                # Task is still running, return last reported progress
                return task.result() if task.done() else None
        return None
