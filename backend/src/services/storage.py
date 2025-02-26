"""Storage service."""

import logging
import os
from typing import Dict, Optional, BinaryIO
from ..utils.logging import log_info, log_error, log_warning
from ..utils.hash_verification import calculate_data_hash, verify_file_hash, HashVerificationError
from ..utils.metrics import (
    STORAGE_OPERATIONS,
    STORAGE_ERRORS,
    STORAGE_SIZE,
    STORAGE_LATENCY,
    track_storage_operation,
    track_storage_error,
    track_storage_size,
    track_storage_latency
)

class StorageService:
    """Service for managing file storage."""

    def __init__(self, settings):
        """Initialize storage service."""
        self.settings = settings
        self.initialized = False

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize storage settings
            self.storage_path = self.settings.get('storage_path')
            self.max_file_size = int(self.settings.get('max_file_size', 104857600))  # 100MB
            self.allowed_extensions = self.settings.get('allowed_extensions', ['.mp3', '.wav', '.m4a'])

            if not self.storage_path:
                raise ValueError("Storage path not configured")

            self.initialized = True
            log_info("Storage service initialized")

        except Exception as e:
            log_error(f"Failed to initialize storage service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Storage service cleaned up")

        except Exception as e:
            log_error(f"Error during storage service cleanup: {str(e)}")
            raise

    async def store_file(self, file_id: str, file: BinaryIO, metadata: Optional[Dict] = None) -> Dict:
        """Store a file and return its metadata including hash."""
        start_time = logging.time()
        try:
            # Track operation
            STORAGE_OPERATIONS.labels(operation='store').inc()
            track_storage_operation('store')

            # Read file data and calculate hash
            file_data = file.read()
            hash_algorithm = "sha256"
            file_hash = calculate_data_hash(file_data, hash_algorithm)

            # Store file
            file_path = await self._store_file(file_id, file_data, metadata)
            
            # Verify hash after storing
            if not verify_file_hash(file_path, file_hash, hash_algorithm):
                # If verification fails, delete file and raise error
                os.remove(file_path)
                raise HashVerificationError("File hash verification failed after storage")
            
            # Track metrics
            file_size = await self._get_file_size(file_path)
            STORAGE_SIZE.inc(file_size)
            track_storage_size(file_size)
            
            duration = logging.time() - start_time
            STORAGE_LATENCY.observe(duration)
            track_storage_latency(duration)
            
            log_info(f"Stored file {file_id} ({file_size} bytes)")
            
            return {
                "file_path": file_path,
                "size": file_size,
                "hash": file_hash,
                "hash_algorithm": hash_algorithm
            }

        except Exception as e:
            STORAGE_ERRORS.inc()
            track_storage_error()
            log_error(f"Error storing file {file_id}: {str(e)}")
            raise

    async def get_file(self, file_id: str) -> Optional[BinaryIO]:
        """Get a file."""
        start_time = logging.time()
        try:
            # Track operation
            STORAGE_OPERATIONS.labels(operation='get').inc()
            track_storage_operation('get')

            # Get file
            file = await self._get_file(file_id)
            
            if file:
                # Track latency
                duration = logging.time() - start_time
                STORAGE_LATENCY.observe(duration)
                track_storage_latency(duration)
                
                log_info(f"Retrieved file {file_id}")
                return file
            
            log_warning(f"File {file_id} not found")
            return None

        except Exception as e:
            STORAGE_ERRORS.inc()
            track_storage_error()
            log_error(f"Error getting file {file_id}: {str(e)}")
            raise

    async def delete_file(self, file_id: str):
        """Delete a file."""
        try:
            # Track operation
            STORAGE_OPERATIONS.labels(operation='delete').inc()
            track_storage_operation('delete')

            # Get file size before deletion
            file_size = await self._get_file_size(file_id)
            
            # Delete file
            deleted = await self._delete_file(file_id)
            
            if deleted:
                # Update storage size
                if file_size:
                    STORAGE_SIZE.dec(file_size)
                    track_storage_size(-file_size)
                log_info(f"Deleted file {file_id}")
            else:
                log_warning(f"File {file_id} not found")

        except Exception as e:
            STORAGE_ERRORS.inc()
            track_storage_error()
            log_error(f"Error deleting file {file_id}: {str(e)}")
            raise

    async def get_file_info(self, file_id: str) -> Optional[Dict]:
        """Get file information."""
        try:
            # Track operation
            STORAGE_OPERATIONS.labels(operation='info').inc()
            track_storage_operation('info')

            # Get info
            info = await self._get_file_info(file_id)
            
            if info:
                log_info(f"Retrieved info for file {file_id}")
                return info
            
            log_warning(f"File {file_id} not found")
            return None

        except Exception as e:
            STORAGE_ERRORS.inc()
            track_storage_error()
            log_error(f"Error getting info for file {file_id}: {str(e)}")
            raise

    async def _store_file(self, file_id: str, file_data: bytes, metadata: Optional[Dict] = None) -> str:
        """Store a file in storage."""
        # Implementation would store file
        file_path = os.path.join(self.storage_path, file_id)
        with open(file_path, 'wb') as f:
            f.write(file_data)
        return file_path

    async def _get_file(self, file_id: str) -> Optional[BinaryIO]:
        """Get a file from storage."""
        # Implementation would get file
        return None

    async def _delete_file(self, file_id: str) -> bool:
        """Delete a file from storage."""
        # Implementation would delete file
        return True

    async def _get_file_info(self, file_id: str) -> Optional[Dict]:
        """Get file information from storage."""
        # Implementation would get file info
        return None

    async def _get_file_size(self, file_id: str) -> Optional[int]:
        """Get file size from storage."""
        # Implementation would get file size
        return None
