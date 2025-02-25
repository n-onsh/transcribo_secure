from typing import Protocol, Optional, List, Dict, Any, BinaryIO, Callable
from datetime import datetime
import uuid
from ..models.job import Job, JobStatus, JobPriority, JobFilter, JobUpdate
from ..models.file_key import FileKey, FileKeyShare, FileKeyCreate, FileKeyShareCreate, FileKeyUpdate

class StorageInterface(Protocol):
    """Interface for storage operations"""
    async def store_file(
        self,
        user_id: str,
        data: BinaryIO,
        file_name: str,
        bucket_type: str,
        file_id: Optional[str] = None,
        compress: bool = True,
        chunk_size: int = 8 * 1024 * 1024,  # 8MB chunks
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> None:
        """Store file in bucket using streaming
        
        Args:
            user_id: User ID
            data: File-like object supporting read()
            file_name: Name of file
            bucket_type: Type of storage bucket
            file_id: Optional file ID for key management
            compress: Whether to compress the file (default True)
            chunk_size: Size of chunks for streaming (default 8MB)
            progress_callback: Optional callback for upload progress (0-100)
        """
        ...

    async def retrieve_file(
        self,
        user_id: str,
        file_name: str,
        bucket: str
    ) -> bytes:
        """Retrieve a file"""
        ...

    async def delete_file(
        self,
        user_id: str,
        file_name: str,
        bucket: str
    ) -> None:
        """Delete a file"""
        ...

    async def get_bucket_size(self, bucket: str) -> int:
        """Get total size of a bucket"""
        ...

class JobManagerInterface(Protocol):
    """Interface for job management"""
    async def create_job(
        self,
        user_id: str,
        file_data: BinaryIO,
        file_name: str,
        priority: JobPriority = JobPriority.NORMAL,
        max_retries: Optional[int] = None
    ) -> Job:
        """Create a new job with streaming file upload
        
        Args:
            user_id: User ID
            file_data: File-like object supporting read()
            file_name: Name of file
            priority: Job priority (default NORMAL)
            max_retries: Maximum retry attempts (optional)
        """
        ...

    async def get_job(
        self,
        job_id: str,
        user_id: Optional[str] = None
    ) -> Optional[Job]:
        """Get job by ID"""
        ...

    async def list_jobs(
        self,
        user_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Job]:
        """List jobs with filtering"""
        ...

    async def update_job(
        self,
        job_id: str,
        update: JobUpdate,
        user_id: Optional[str] = None
    ) -> Job:
        """Update job"""
        ...

    async def delete_job(
        self,
        job_id: str,
        user_id: Optional[str] = None
    ) -> None:
        """Delete job"""
        ...

    async def cancel_job(
        self,
        job_id: str,
        user_id: Optional[str] = None
    ) -> Job:
        """Cancel job"""
        ...

    async def retry_job(
        self,
        job_id: str,
        user_id: Optional[str] = None
    ) -> Job:
        """Retry job"""
        ...

class DatabaseInterface(Protocol):
    """Interface for database operations"""
    async def initialize_database(self) -> None:
        """Initialize database connection and schema"""
        ...

    async def claim_job(self, worker_id: str) -> Optional[Job]:
        """Claim next available job"""
        ...

    async def release_stale_jobs(
        self,
        max_lock_duration_minutes: int = 30
    ) -> int:
        """Release jobs with stale locks"""
        ...

    async def create_file_key(self, file_key: FileKeyCreate) -> FileKey:
        """Create file key"""
        ...

    async def get_file_key(self, file_id: uuid.UUID) -> Optional[FileKey]:
        """Get file key"""
        ...

    async def update_file_key(
        self,
        file_id: uuid.UUID,
        update: FileKeyUpdate
    ) -> Optional[FileKey]:
        """Update file key"""
        ...

    async def delete_file_key(self, file_id: uuid.UUID) -> bool:
        """Delete file key"""
        ...

    async def create_file_key_share(
        self,
        share: FileKeyShareCreate
    ) -> FileKeyShare:
        """Create file key share"""
        ...

    async def get_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Optional[FileKeyShare]:
        """Get file key share"""
        ...

    async def list_file_key_shares(
        self,
        file_id: uuid.UUID
    ) -> List[FileKeyShare]:
        """List file key shares"""
        ...

    async def update_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID,
        update: FileKeyUpdate
    ) -> Optional[FileKeyShare]:
        """Update file key share"""
        ...

    async def delete_file_key_share(
        self,
        file_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> bool:
        """Delete file key share"""
        ...

    async def delete_all_file_key_shares(self, file_id: uuid.UUID) -> int:
        """Delete all file key shares for a file"""
        ...

    async def get_active_connections(self) -> int:
        """Get number of active database connections"""
        ...

    async def close(self) -> None:
        """Close database connections"""
        ...

class KeyManagementInterface(Protocol):
    """Interface for key management operations"""
    async def get_key(self, key_name: str) -> bytes:
        """Get encryption key"""
        ...

    async def create_key(self, key_name: str, key_value: bytes) -> None:
        """Create encryption key"""
        ...

    async def delete_key(self, key_name: str) -> None:
        """Delete encryption key"""
        ...

    async def rotate_key(self, key_name: str) -> bytes:
        """Rotate encryption key"""
        ...

    async def list_keys(self) -> List[str]:
        """List available keys"""
        ...

class EncryptionInterface(Protocol):
    """Interface for encryption operations"""
    async def encrypt(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data"""
        ...

    async def decrypt(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data"""
        ...

    async def generate_key(self) -> bytes:
        """Generate new encryption key"""
        ...

    async def derive_key(self, master_key: bytes, salt: bytes) -> bytes:
        """Derive encryption key"""
        ...
