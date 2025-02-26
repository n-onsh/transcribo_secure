"""Vocabulary routes."""

from typing import Dict, List
from fastapi import APIRouter, HTTPException
from ..services.vocabulary import VocabularyService
from ..utils.logging import log_error

router = APIRouter()
vocabulary_service = None  # Will be initialized by service provider

@router.post("/api/jobs/{job_id}/vocabulary")
async def add_job_vocabulary(job_id: str, vocabulary_items: List[Dict]):
    """Add vocabulary items to a job."""
    try:
        if not vocabulary_service:
            raise ValueError("Vocabulary service not initialized")

        success = await vocabulary_service.apply_vocabulary_to_job(job_id, vocabulary_items)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply vocabulary")
        
        return {"status": "success"}
    except Exception as e:
        log_error(f"Error adding vocabulary for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/jobs/{job_id}/vocabulary")
async def get_job_vocabulary(job_id: str):
    """Get vocabulary items for a job."""
    try:
        if not vocabulary_service:
            raise ValueError("Vocabulary service not initialized")

        items = await vocabulary_service.get_job_vocabulary(job_id)
        return {"vocabulary": items}
    except Exception as e:
        log_error(f"Error getting vocabulary for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/jobs/{job_id}/vocabulary")
async def delete_job_vocabulary(job_id: str):
    """Delete vocabulary items for a job."""
    try:
        if not vocabulary_service:
            raise ValueError("Vocabulary service not initialized")

        success = await vocabulary_service.delete_job_vocabulary(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Vocabulary not found")
        
        return {"status": "success"}
    except Exception as e:
        log_error(f"Error deleting vocabulary for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def initialize(service: VocabularyService):
    """Initialize the vocabulary routes with required services."""
    global vocabulary_service
    vocabulary_service = service
