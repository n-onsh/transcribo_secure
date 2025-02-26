"""Service interfaces."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class StorageInterface(ABC):
    """Interface for storage service."""

    @abstractmethod
    async def store_file(self, file_data: bytes, file_name: str) -> str:
        """Store a file and return its ID."""
        pass

    @abstractmethod
    async def get_file(self, file_id: str) -> bytes:
        """Get a file by its ID."""
        pass

    @abstractmethod
    async def delete_file(self, file_id: str) -> bool:
        """Delete a file by its ID."""
        pass

class JobManagerInterface(ABC):
    """Interface for job manager service."""

    @abstractmethod
    async def create_job(self, job_data: Dict) -> str:
        """Create a new job."""
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Dict:
        """Get a job by its ID."""
        pass

    @abstractmethod
    async def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update a job."""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        pass

class VocabularyInterface(ABC):
    """Interface for vocabulary service."""

    @abstractmethod
    async def add_word(self, word: str, language: str) -> bool:
        """Add a word to the vocabulary."""
        pass

    @abstractmethod
    async def get_words(self, language: str) -> List[str]:
        """Get all words for a language."""
        pass

    @abstractmethod
    async def remove_word(self, word: str, language: str) -> bool:
        """Remove a word from the vocabulary."""
        pass

class ZipHandlerInterface(ABC):
    """Interface for ZIP handler service."""

    @abstractmethod
    async def create_zip(self, files: List[Dict]) -> bytes:
        """Create a ZIP file from multiple files."""
        pass

    @abstractmethod
    async def extract_zip(self, zip_data: bytes) -> List[Dict]:
        """Extract files from a ZIP file."""
        pass

class ViewerInterface(ABC):
    """Interface for viewer service."""

    @abstractmethod
    async def get_preview(self, file_id: str) -> Dict:
        """Get a preview of a file."""
        pass

    @abstractmethod
    async def get_thumbnail(self, file_id: str) -> bytes:
        """Get a thumbnail of a file."""
        pass

class TagServiceInterface(ABC):
    """Interface for tag service."""

    @abstractmethod
    async def create_tag(self, tag_data: Dict, user_id: str) -> str:
        """Create a new tag."""
        pass

    @abstractmethod
    async def get_tag(self, tag_id: str) -> Dict:
        """Get a tag by its ID."""
        pass

    @abstractmethod
    async def get_tags(self, user_id: str) -> List[Dict]:
        """Get all tags for a user."""
        pass

    @abstractmethod
    async def update_tag(self, tag_id: str, updates: Dict) -> bool:
        """Update a tag."""
        pass

    @abstractmethod
    async def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag."""
        pass

    @abstractmethod
    async def assign_tag(self, tag_id: str, resource_id: str, resource_type: str, user_id: str) -> str:
        """Assign a tag to a resource."""
        pass

    @abstractmethod
    async def remove_tag(self, tag_id: str, resource_id: str, resource_type: str) -> bool:
        """Remove a tag from a resource."""
        pass

    @abstractmethod
    async def get_resource_tags(self, resource_id: str, resource_type: str) -> List[Dict]:
        """Get all tags for a resource."""
        pass

    @abstractmethod
    async def get_resources_by_tag(self, tag_id: str, resource_type: Optional[str] = None) -> List[str]:
        """Get all resources with a specific tag."""
        pass
