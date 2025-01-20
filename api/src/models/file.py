from datetime import datetime
from pydantic import BaseModel, UUID4
from typing import Optional

class FileMetadata(BaseModel):
    file_id: UUID4
    user_id: str
    file_name: str
    file_type: str
    created_at: datetime
    size_bytes: int
    content_type: Optional[str] = None