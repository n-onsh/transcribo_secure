from fastapi import APIRouter, HTTPException, Depends
from uuid import uuid4
from typing import List
from ..models.vocabulary import VocabularyCreate, VocabularyResponse
from ..services.database import DatabaseService

router = APIRouter()

@router.post("/vocabulary", response_model=VocabularyResponse)
async def create_vocabulary(
    vocab: VocabularyCreate,
    user_id: str = "test_user",  # We'll implement proper auth later
    db: DatabaseService = Depends(DatabaseService)
):
    """Create or update vocabulary for a user"""
    try:
        # Delete existing vocabulary
        await db.delete_user_vocabulary(user_id)
        
        # Add new words
        words = []
        for word in vocab.words:
            word_id = await db.create_vocabulary_word(
                id=uuid4(),
                user_id=user_id,
                word=word.strip()
            )
            words.append(word)
            
        return VocabularyResponse(words=words)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/vocabulary", response_model=VocabularyResponse)
async def get_vocabulary(
    user_id: str = "test_user",
    db: DatabaseService = Depends(DatabaseService)
):
    """Get vocabulary for a user"""
    words = await db.get_user_vocabulary(user_id)
    return VocabularyResponse(words=words)