from fastapi import APIRouter, Depends, HTTPException, Request, Query
from typing import List, Optional
from datetime import datetime
import logging
from ..services.vocabulary import VocabularyService
from ..models.vocabulary import (
    VocabularyList,
    VocabularyUpdate,
    VocabularyFilter,
    VocabularySort,
    VocabularyStats
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/vocabulary",
    tags=["vocabulary"]
)

# Initialize service
vocabulary = VocabularyService()

@router.get("/words")
async def get_words(
    request: Request,
    prefix: Optional[str] = Query(None, description="Filter words by prefix"),
    min_length: Optional[int] = Query(None, description="Minimum word length"),
    max_length: Optional[int] = Query(None, description="Maximum word length"),
    sort_by: Optional[str] = Query("word", description="Sort field (word, added_at)"),
    ascending: bool = Query(True, description="Sort direction")
) -> List[str]:
    """Get user's vocabulary words"""
    try:
        # Get user from request state (set by auth middleware)
        user = request.state.user
        
        # Get vocabulary
        vocab = await vocabulary.get_vocabulary(user["id"])
        
        # Apply filter
        filter = VocabularyFilter(
            prefix=prefix,
            min_length=min_length,
            max_length=max_length
        )
        filtered = filter.apply(vocab)
        
        # Apply sort
        sort = VocabularySort(field=sort_by, ascending=ascending)
        return sort.apply(vocab)
        
    except Exception as e:
        logger.error(f"Failed to get vocabulary words: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get vocabulary")

@router.post("/words")
async def add_words(
    request: Request,
    words: List[str]
) -> VocabularyList:
    """Add words to vocabulary"""
    try:
        user = request.state.user
        return await vocabulary.add_words(user["id"], words)
        
    except Exception as e:
        logger.error(f"Failed to add vocabulary words: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add words")

@router.delete("/words")
async def remove_words(
    request: Request,
    words: List[str]
) -> VocabularyList:
    """Remove words from vocabulary"""
    try:
        user = request.state.user
        return await vocabulary.remove_words(user["id"], words)
        
    except Exception as e:
        logger.error(f"Failed to remove vocabulary words: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove words")

@router.get("")
async def get_vocabulary(request: Request) -> VocabularyList:
    """Get user's complete vocabulary list"""
    try:
        user = request.state.user
        return await vocabulary.get_vocabulary(user["id"])
        
    except Exception as e:
        logger.error(f"Failed to get vocabulary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get vocabulary")

@router.put("")
async def update_vocabulary(
    request: Request,
    update: VocabularyUpdate
) -> VocabularyList:
    """Update vocabulary list"""
    try:
        user = request.state.user
        return await vocabulary.update_vocabulary(user["id"], update)
        
    except Exception as e:
        logger.error(f"Failed to update vocabulary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update vocabulary")

@router.delete("")
async def clear_vocabulary(request: Request):
    """Clear vocabulary list"""
    try:
        user = request.state.user
        await vocabulary.clear_vocabulary(user["id"])
        
    except Exception as e:
        logger.error(f"Failed to clear vocabulary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear vocabulary")

@router.get("/stats")
async def get_stats(request: Request) -> VocabularyStats:
    """Get vocabulary statistics"""
    try:
        user = request.state.user
        vocab = await vocabulary.get_vocabulary(user["id"])
        return VocabularyStats.from_vocabulary(vocab)
        
    except Exception as e:
        logger.error(f"Failed to get vocabulary stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get vocabulary stats")

@router.post("/import")
async def import_vocabulary(
    request: Request,
    words: List[str]
) -> VocabularyList:
    """Import vocabulary words"""
    try:
        user = request.state.user
        
        # Create update
        update = VocabularyUpdate(add=words)
        
        # Apply update
        return await vocabulary.update_vocabulary(user["id"], update)
        
    except Exception as e:
        logger.error(f"Failed to import vocabulary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import vocabulary")

@router.get("/export")
async def export_vocabulary(
    request: Request,
    format: str = Query("txt", description="Export format (txt, json)")
) -> str:
    """Export vocabulary words"""
    try:
        user = request.state.user
        vocab = await vocabulary.get_vocabulary(user["id"])
        
        if format == "json":
            return vocab.json(indent=2)
        else:  # txt
            return "\n".join(vocab.get_words())
            
    except Exception as e:
        logger.error(f"Failed to export vocabulary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export vocabulary")

@router.post("/merge")
async def merge_vocabularies(
    request: Request,
    other_user_id: str
) -> VocabularyList:
    """Merge vocabulary with another user's"""
    try:
        user = request.state.user
        
        # Get vocabularies
        vocab = await vocabulary.get_vocabulary(user["id"])
        other = await vocabulary.get_vocabulary(other_user_id)
        
        # Merge
        vocab.merge(other)
        
        # Save changes
        await vocabulary._save_vocabulary(vocab)
        
        return vocab
        
    except Exception as e:
        logger.error(f"Failed to merge vocabularies: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to merge vocabularies")
