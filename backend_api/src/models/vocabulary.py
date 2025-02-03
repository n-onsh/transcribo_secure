from datetime import datetime
from pydantic import BaseModel, UUID4
from typing import List

class VocabularyWord(BaseModel):
    id: UUID4
    user_id: str
    word: str
    created_at: datetime
    updated_at: datetime

class VocabularyCreate(BaseModel):
    words: List[str]

class VocabularyResponse(BaseModel):
    words: List[str]