"""Service interfaces."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Set, Tuple
from uuid import UUID

class DatabaseInterface(ABC):
    """Database service interface."""

    @abstractmethod
    async def initialize_database(self) -> None:
        """Initialize database."""
        pass

    @abstractmethod
    async def get_active_connections(self) -> int:
        """Get number of active connections."""
        pass

class StorageInterface(ABC):
    """Storage service interface."""

    @abstractmethod
    async def upload_file(self, file: 'File', file_path: str) -> None:
        """Upload file to storage."""
        pass

    @abstractmethod
    async def download_file(self, file: 'File', target_path: str) -> None:
        """Download file from storage."""
        pass

    @abstractmethod
    async def delete_file(self, file: 'File') -> None:
        """Delete file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, file_name: str) -> bool:
        """Check if file exists in storage."""
        pass

    @abstractmethod
    async def get_bucket_size(self, bucket: str) -> int:
        """Get total size of bucket in bytes."""
        pass

class JobManagerInterface(ABC):
    """Job manager service interface."""

    @abstractmethod
    async def start(self) -> None:
        """Start job manager."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop job manager."""
        pass

    @abstractmethod
    async def create_job(self, job: 'Job', language: Optional[str] = None) -> None:
        """Create new job."""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: UUID) -> None:
        """Cancel job."""
        pass

    @abstractmethod
    async def get_job_status(self, job_id: UUID) -> str:
        """Get job status."""
        pass

class KeyManagementInterface(ABC):
    """Key management service interface."""

    @abstractmethod
    def generate_key(self) -> bytes:
        """Generate new encryption key."""
        pass

    @abstractmethod
    def store_key(self, key_id: UUID, key: bytes) -> None:
        """Store encryption key."""
        pass

    @abstractmethod
    def get_key(self, key_id: UUID) -> Optional[bytes]:
        """Get encryption key."""
        pass

    @abstractmethod
    def delete_key(self, key_id: UUID) -> None:
        """Delete encryption key."""
        pass

class EncryptionInterface(ABC):
    """Encryption service interface."""

    @abstractmethod
    def encrypt_file(self, file_path: str, key: bytes) -> None:
        """Encrypt file in place."""
        pass

    @abstractmethod
    def decrypt_file(self, file_path: str, key: bytes) -> None:
        """Decrypt file in place."""
        pass

    @abstractmethod
    def encrypt_data(self, data: bytes, key: bytes) -> bytes:
        """Encrypt data."""
        pass

    @abstractmethod
    def decrypt_data(self, data: bytes, key: bytes) -> bytes:
        """Decrypt data."""
        pass

class ZipHandlerInterface(ABC):
    """ZIP handler service interface."""

    @abstractmethod
    async def validate_zip(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """Validate ZIP file before extraction."""
        pass

    @abstractmethod
    async def extract_zip(
        self,
        file_id: UUID,
        owner_id: UUID,
        file_path: str,
        language: Optional[str] = None
    ) -> AsyncGenerator[Tuple[str, float], None]:
        """Extract and process ZIP contents."""
        pass

    @abstractmethod
    async def cancel_extraction(self, file_id: UUID) -> None:
        """Cancel ZIP extraction."""
        pass

    @abstractmethod
    async def get_extraction_progress(self, file_id: UUID) -> Optional[float]:
        """Get progress of ongoing extraction."""
        pass
