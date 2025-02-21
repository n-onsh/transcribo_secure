from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, List, Optional
import logging
from ..models.job import Job, JobStatus, TranscriptionUpdate
from ..services.storage import StorageService
from ..services.job_manager import JobManager
from ..services.viewer import ViewerService
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transcriber",
    tags=["transcriber"]
)

# Service dependencies
async def get_storage() -> StorageService:
    return StorageService()

async def get_job_manager() -> JobManager:
    return JobManager()

async def get_viewer_service() -> ViewerService:
    return ViewerService()

@router.get("/{job_id}")
async def get_transcription(
    job_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Get transcription data with media URL"""
    try:
        # Get user from request state (set by auth middleware)
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get transcription data
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Get media file
        media = await storage.retrieve_file(
            user["id"],
            job.file_name,
            "audio"
        )
        
        # Generate temporary media URL
        media_url = await storage.get_presigned_url(
            user["id"],
            job.file_name,
            "audio",
            expires_in=3600  # 1 hour
        )
        
        # Combine data
        response = {
            "job_id": job_id,
            "file_name": job.file_name,
            "created_at": job.created_at.isoformat(),
            "media_type": "video" if job.file_name.lower().endswith((".mp4", ".mov", ".avi")) else "audio",
            "media_url": media_url,
            "duration": job.duration,
            **transcription
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Error getting transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get transcription")

@router.post("/{job_id}/save")
async def save_transcription(
    job_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Save transcription changes"""
    try:
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get current transcription
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Create backup
        await storage.store_file(
            user["id"],
            transcription,
            f"{job_id}_{datetime.utcnow().isoformat()}.json",
            "transcription"
        )
        
        # Update transcription
        await storage.store_file(
            user["id"],
            request.json(),
            f"{job_id}.json",
            "transcription"
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error saving transcription: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save transcription")

@router.put("/{job_id}/speakers/{speaker_idx}")
async def update_speaker(
    job_id: str,
    speaker_idx: int,
    name: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Update speaker name"""
    try:
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get transcription
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Update speaker
        if speaker_idx >= len(transcription["speakers"]):
            raise HTTPException(status_code=400, detail="Invalid speaker index")
            
        transcription["speakers"][speaker_idx]["name"] = name
        
        # Save changes
        await storage.store_file(
            user["id"],
            transcription,
            f"{job_id}.json",
            "transcription"
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error updating speaker: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update speaker")

@router.put("/{job_id}/segments/{segment_id}")
async def update_segment(
    job_id: str,
    segment_id: str,
    data: Dict,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Update segment data"""
    try:
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get transcription
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Find and update segment
        segment_found = False
        for segment in transcription["segments"]:
            if segment["id"] == segment_id:
                segment.update(data)
                segment_found = True
                break
                
        if not segment_found:
            raise HTTPException(status_code=404, detail="Segment not found")
            
        # Save changes
        await storage.store_file(
            user["id"],
            transcription,
            f"{job_id}.json",
            "transcription"
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error updating segment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update segment")

@router.delete("/{job_id}/segments/{segment_id}")
async def delete_segment(
    job_id: str,
    segment_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Delete a segment"""
    try:
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get transcription
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Remove segment
        transcription["segments"] = [
            s for s in transcription["segments"]
            if s["id"] != segment_id
        ]
        
        # Save changes
        await storage.store_file(
            user["id"],
            transcription,
            f"{job_id}.json",
            "transcription"
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error deleting segment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete segment")

@router.post("/{job_id}/segments")
async def add_segment(
    job_id: str,
    after_id: str,
    request: Request,
    storage: StorageService = Depends(get_storage),
    job_manager: JobManager = Depends(get_job_manager)
) -> Dict:
    """Add a new segment after the specified one"""
    try:
        user = request.state.user
        
        # Get job
        job = await job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Verify ownership
        if job.user_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
            
        # Get transcription
        transcription = await storage.retrieve_file(
            user["id"],
            f"{job_id}.json",
            "transcription"
        )
        
        # Find reference segment
        for i, segment in enumerate(transcription["segments"]):
            if segment["id"] == after_id:
                # Create new segment
                new_segment = {
                    "id": str(uuid.uuid4()),
                    "start": segment["end"],
                    "end": segment["end"] + 1.0,
                    "text": "New segment",
                    "speaker_idx": segment["speaker_idx"],
                    "is_foreign_language": False
                }
                
                # Insert after reference segment
                transcription["segments"].insert(i + 1, new_segment)
                
                # Save changes
                await storage.store_file(
                    user["id"],
                    transcription,
                    f"{job_id}.json",
                    "transcription"
                )
                
                return {"status": "success", "segment": new_segment}
                
        raise HTTPException(status_code=404, detail="Reference segment not found")
        
    except Exception as e:
        logger.error(f"Error adding segment: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add segment")
