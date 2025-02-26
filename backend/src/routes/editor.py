"""Editor routes."""

import logging
from typing import Dict, List
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from ..services.job_manager import JobManager
from ..services.transcription import TranscriptionService
from ..services.storage import StorageService
from ..services.viewer import ViewerService
from ..utils.logging import log_info, log_error

router = APIRouter()

@router.get("/api/editor/{job_id}/download")
async def download_editor(job_id: str) -> HTMLResponse:
    """Get downloadable editor."""
    try:
        # Get job
        job = await JobManager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get transcription
        transcription = await TranscriptionService.get_transcription(job.file_id)
        
        # Get audio/video file URL
        media_url = await StorageService.get_file_url(job.file_id)

        # Read editor template
        with open("backend/src/templates/editor.html", "r") as f:
            template = f.read()

        # Read editor JavaScript
        with open("backend/src/assets/editor.js", "r") as f:
            js = f.read()

        # Replace template variables
        html = template.replace(
            '<script src="/assets/editor.js"></script>',
            f'<script>\n{js}\n</script>'
        ).replace(
            '{{ job_id }}',
            job_id
        ).replace(
            '{{ media_url }}',
            media_url
        ).replace(
            '{{ transcription|tojson }}',
            str(transcription)
        )

        return HTMLResponse(content=html)

    except Exception as e:
        log_error(f"Error getting downloadable editor for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/editor/{job_id}")
async def get_editor(job_id: str, request: Request):
    """Get editor data."""
    try:
        # Get job
        job = await JobManager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get transcription
        transcription = await TranscriptionService.get_transcription(job.file_id)
        
        # Get audio/video file URL
        media_url = await StorageService.get_file_url(job.file_id)
        
        return {
            "job": job,
            "transcription": transcription,
            "media_url": media_url
        }
    except Exception as e:
        log_error(f"Error getting editor data for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/editor/{job_id}/speakers")
async def update_speakers(job_id: str, speakers: List[Dict]):
    """Update speaker information for a transcription."""
    try:
        updated = await TranscriptionService.update_speakers(job_id, speakers)
        return {"status": "success", "transcription": updated}
    except Exception as e:
        log_error(f"Error updating speakers for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/editor/{job_id}/segments")
async def update_segments(job_id: str, segments: List[Dict]):
    """Update segments for a transcription."""
    try:
        # Get job
        job = await JobManager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get transcription
        transcription = await TranscriptionService.get_transcription(job.file_id)
        
        # Replace segments
        transcription["segments"] = segments
        
        # Save updated transcription
        await TranscriptionService.save_transcription(job.file_id, transcription)
        
        return {"status": "success", "transcription": transcription}
    except Exception as e:
        log_error(f"Error updating segments for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/editor/{job_id}/segments/add")
async def add_segment(job_id: str, segment: Dict):
    """Add a new segment to a transcription."""
    try:
        # Get job
        job = await JobManager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get transcription
        transcription = await TranscriptionService.get_transcription(job.file_id)
        
        # Add new segment
        new_segment = {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"],
            "speaker": segment["speaker"],
            "language": segment["language"]
        }
        
        # Insert in correct position based on start time
        segments = transcription.get("segments", [])
        insert_index = 0
        for i, s in enumerate(segments):
            if s["start"] > segment["start"]:
                insert_index = i
                break
            insert_index = i + 1
        
        segments.insert(insert_index, new_segment)
        transcription["segments"] = segments
        
        # Save updated transcription
        await TranscriptionService.save_transcription(job.file_id, transcription)
        
        return {"status": "success", "transcription": transcription}
    except Exception as e:
        log_error(f"Error adding segment for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/api/editor/{job_id}/segments/{segment_index}")
async def delete_segment(job_id: str, segment_index: int):
    """Delete a segment from a transcription."""
    try:
        # Get job
        job = await JobManager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get transcription
        transcription = await TranscriptionService.get_transcription(job.file_id)
        
        # Delete segment
        segments = transcription.get("segments", [])
        if segment_index < 0 or segment_index >= len(segments):
            raise HTTPException(status_code=400, detail="Invalid segment index")
        
        segments.pop(segment_index)
        transcription["segments"] = segments
        
        # Save updated transcription
        await TranscriptionService.save_transcription(job.file_id, transcription)
        
        return {"status": "success", "transcription": transcription}
    except Exception as e:
        log_error(f"Error deleting segment for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
