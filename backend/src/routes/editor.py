"""Editor routes."""

import logging
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Request, Response, Depends, status
from fastapi.responses import HTMLResponse
from ..services.job_manager import JobManager
from ..services.transcription import TranscriptionService
from ..services.storage import StorageService
from ..services.viewer import ViewerService
from ..utils.logging import log_info, log_error
from ..utils.exceptions import (
    ResourceNotFoundError,
    ValidationError,
    TranscriboError
)
from ..utils.metrics import track_time, DB_OPERATION_DURATION
from ..utils.dependencies import (
    JobManager as JobManagerDep,
    TranscriptionService as TranscriptionDep,
    StorageService as StorageDep,
    ViewerService as ViewerDep
)

# Response models
class EditorResponse(BaseModel):
    """Editor data response."""
    job: Dict
    transcription: Dict
    media_url: str

class SpeakerUpdate(BaseModel):
    """Speaker update request."""
    id: str
    name: str

class SegmentUpdate(BaseModel):
    """Segment update request."""
    start: float
    end: float
    text: str
    speaker: str
    language: Optional[str] = None

class TranscriptionResponse(BaseModel):
    """Transcription update response."""
    status: str
    transcription: Dict

router = APIRouter(
    prefix="/api/editor",
    tags=["editor"]
)

@router.get("/{job_id}/download")
@track_time(DB_OPERATION_DURATION, {"operation": "download_editor"})
async def download_editor(
    job_id: str,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep),
    storage: StorageService = Depends(StorageDep)
) -> HTMLResponse:
    """Get downloadable editor."""
    try:
        # Get job
        job = await job_manager.get_job(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(job.file_id)
        
        # Get audio/video file URL
        media_url = await storage.get_file_url(job.file_id)

        # Read template files
        template_path = Path("backend/src/templates/editor.html")
        js_path = Path("backend/src/assets/editor.js")
        
        if not template_path.exists() or not js_path.exists():
            raise TranscriboError("Editor template files not found")

        template = template_path.read_text()
        js = js_path.read_text()

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
            str(transcription_data)
        )

        return HTMLResponse(content=html)

    except ResourceNotFoundError:
        raise
    except TranscriboError:
        raise
    except Exception as e:
        log_error(f"Error getting downloadable editor for job {job_id}: {str(e)}")
        raise TranscriboError(
            "Failed to generate downloadable editor",
            details={"job_id": job_id, "error": str(e)}
        )

@router.get("/{job_id}", response_model=EditorResponse)
@track_time(DB_OPERATION_DURATION, {"operation": "get_editor"})
async def get_editor(
    job_id: str,
    request: Request,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep),
    storage: StorageService = Depends(StorageDep)
):
    """Get editor data."""
    # Get job
    job = await job_manager.get_job(job_id)
    
    # Get transcription
    transcription_data = await transcription.get_transcription(job.file_id)
    
    # Get audio/video file URL
    media_url = await storage.get_file_url(job.file_id)
    
    return EditorResponse(
        job=job.dict(),
        transcription=transcription_data,
        media_url=media_url
    )

@router.post("/{job_id}/speakers", response_model=TranscriptionResponse)
@track_time(DB_OPERATION_DURATION, {"operation": "update_speakers"})
async def update_speakers(
    job_id: str,
    speakers: List[SpeakerUpdate],
    transcription: TranscriptionService = Depends(TranscriptionDep)
):
    """Update speaker information for a transcription."""
    updated = await transcription.update_speakers(job_id, [s.dict() for s in speakers])
    return TranscriptionResponse(status="success", transcription=updated)

@router.post("/{job_id}/segments", response_model=TranscriptionResponse)
@track_time(DB_OPERATION_DURATION, {"operation": "update_segments"})
async def update_segments(
    job_id: str,
    segments: List[SegmentUpdate],
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
):
    """Update segments for a transcription."""
    # Get job
    job = await job_manager.get_job(job_id)
    
    # Get transcription
    transcription_data = await transcription.get_transcription(job.file_id)
    
    # Replace segments
    transcription_data["segments"] = [s.dict() for s in segments]
    
    # Save updated transcription
    await transcription.save_transcription(job.file_id, transcription_data)
    
    return TranscriptionResponse(status="success", transcription=transcription_data)

@router.post("/{job_id}/segments/add", response_model=TranscriptionResponse)
@track_time(DB_OPERATION_DURATION, {"operation": "add_segment"})
async def add_segment(
    job_id: str,
    segment: SegmentUpdate,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
):
    """Add a new segment to a transcription."""
    # Get job
    job = await job_manager.get_job(job_id)
    
    # Get transcription
    transcription_data = await transcription.get_transcription(job.file_id)
    
    # Insert in correct position based on start time
    segments = transcription_data.get("segments", [])
    insert_index = 0
    for i, s in enumerate(segments):
        if s["start"] > segment.start:
            insert_index = i
            break
        insert_index = i + 1
    
    segments.insert(insert_index, segment.dict())
    transcription_data["segments"] = segments
    
    # Save updated transcription
    await transcription.save_transcription(job.file_id, transcription_data)
    
    return TranscriptionResponse(status="success", transcription=transcription_data)

@router.delete("/{job_id}/segments/{segment_index}", response_model=TranscriptionResponse)
@track_time(DB_OPERATION_DURATION, {"operation": "delete_segment"})
async def delete_segment(
    job_id: str,
    segment_index: int,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
):
    """Delete a segment from a transcription."""
    # Get job
    job = await job_manager.get_job(job_id)
    
    # Get transcription
    transcription_data = await transcription.get_transcription(job.file_id)
    
    # Delete segment
    segments = transcription_data.get("segments", [])
    if segment_index < 0 or segment_index >= len(segments):
        raise ValidationError("Invalid segment index")
    
    segments.pop(segment_index)
    transcription_data["segments"] = segments
    
    # Save updated transcription
    await transcription.save_transcription(job.file_id, transcription_data)
    
    return TranscriptionResponse(status="success", transcription=transcription_data)
