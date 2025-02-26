"""Editor routes."""

import logging
from pathlib import Path
from typing import Dict, List, Optional, cast
from datetime import datetime
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
    TranscriboError,
    EditorError
)
from ..types import (
    ErrorContext,
    JobID,
    FileID,
    EditorSegment,
    EditorSpeaker,
    EditorData,
    EditorTemplate,
    EditorUpdate
)
from ..utils.route_utils import (
    route_handler,
    map_to_response
)
from ..utils.dependencies import (
    JobManagerDep,
    TranscriptionDep,
    StorageDep,
    ViewerDep
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

async def _load_editor_template(job_id: JobID, media_url: str, transcription_data: Dict) -> str:
    """Load and populate editor template.
    
    Args:
        job_id: Job ID for the editor
        media_url: URL for the media file
        transcription_data: Transcription data to embed
        
    Returns:
        Populated HTML template
        
    Raises:
        EditorError: If template files not found or invalid
    """
    try:
        # Read template files
        template_path = Path("backend/src/templates/editor.html")
        js_path = Path("backend/src/assets/editor.js")
        
        if not template_path.exists() or not js_path.exists():
            error_context: ErrorContext = {
                "operation": "load_template",
                "timestamp": datetime.utcnow(),
                "details": {
                    "template_path": str(template_path),
                    "js_path": str(js_path)
                }
            }
            raise EditorError("Editor template files not found", details=error_context)

        template = template_path.read_text()
        js = js_path.read_text()

        # Replace template variables
        return template.replace(
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

    except EditorError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "load_template",
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise EditorError("Failed to load editor template", details=error_context)

@router.get("/{job_id}/download")
@route_handler("download_editor")
async def download_editor(
    job_id: JobID,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep),
    storage: StorageService = Depends(StorageDep)
) -> HTMLResponse:
    """Get downloadable editor.
    
    Args:
        job_id: Job ID to get editor for
        job_manager: Job manager service
        transcription: Transcription service
        storage: Storage service
        
    Returns:
        HTML response with embedded editor
        
    Raises:
        ResourceNotFoundError: If job not found
        EditorError: If editor generation fails
        TranscriboError: If operation fails
    """
    try:
        # Get job
        job = await job_manager.get_job_status(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(cast(FileID, job.get('file_id')))
        
        # Get audio/video file URL
        media_url = await storage.get_file_url(cast(FileID, job.get('file_id')))

        # Load and populate template
        html = await _load_editor_template(job_id, media_url, transcription_data)

        return HTMLResponse(content=html)

    except (ResourceNotFoundError, EditorError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "download_editor",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        log_error(f"Error getting downloadable editor for job {job_id}: {str(e)}")
        raise TranscriboError("Failed to generate downloadable editor", details=error_context)

@router.get("/{job_id}", response_model=EditorResponse)
@route_handler("get_editor", EditorResponse)
async def get_editor(
    job_id: JobID,
    request: Request,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep),
    storage: StorageService = Depends(StorageDep)
) -> EditorResponse:
    """Get editor data.
    
    Args:
        job_id: Job ID to get editor for
        request: FastAPI request
        job_manager: Job manager service
        transcription: Transcription service
        storage: Storage service
        
    Returns:
        Editor response with job, transcription and media URL
        
    Raises:
        ResourceNotFoundError: If job not found
        TranscriboError: If operation fails
    """
    try:
        # Get job
        job = await job_manager.get_job_status(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(cast(FileID, job.get('file_id')))
        
        # Get audio/video file URL
        media_url = await storage.get_file_url(cast(FileID, job.get('file_id')))
        
        return EditorResponse(
            job=job,
            transcription=transcription_data,
            media_url=media_url
        )
        
    except ResourceNotFoundError:
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "get_editor",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to get editor data", details=error_context)

@router.post("/{job_id}/speakers", response_model=TranscriptionResponse)
@route_handler("update_speakers", TranscriptionResponse)
async def update_speakers(
    job_id: JobID,
    speakers: List[SpeakerUpdate],
    transcription: TranscriptionService = Depends(TranscriptionDep)
) -> TranscriptionResponse:
    """Update speaker information for a transcription.
    
    Args:
        job_id: Job ID to update speakers for
        speakers: List of speaker updates
        transcription: Transcription service
        
    Returns:
        Updated transcription response
        
    Raises:
        ResourceNotFoundError: If job not found
        ValidationError: If speaker data invalid
        TranscriboError: If operation fails
    """
    try:
        updated = await transcription.update_speakers(job_id, [s.dict() for s in speakers])
        return TranscriptionResponse(status="success", transcription=updated)
        
    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "update_speakers",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to update speakers", details=error_context)

@router.post("/{job_id}/segments", response_model=TranscriptionResponse)
@route_handler("update_segments", TranscriptionResponse)
async def update_segments(
    job_id: JobID,
    segments: List[SegmentUpdate],
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
) -> TranscriptionResponse:
    """Update segments for a transcription.
    
    Args:
        job_id: Job ID to update segments for
        segments: List of segment updates
        job_manager: Job manager service
        transcription: Transcription service
        
    Returns:
        Updated transcription response
        
    Raises:
        ResourceNotFoundError: If job not found
        ValidationError: If segment data invalid
        TranscriboError: If operation fails
    """
    try:
        # Get job
        job = await job_manager.get_job_status(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(cast(FileID, job.get('file_id')))
        
        # Replace segments
        transcription_data["segments"] = [s.dict() for s in segments]
        
        # Save updated transcription
        await transcription.save_transcription(cast(FileID, job.get('file_id')), transcription_data)
        
        return TranscriptionResponse(status="success", transcription=transcription_data)
        
    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "update_segments",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {"error": str(e)}
        }
        raise TranscriboError("Failed to update segments", details=error_context)

@router.post("/{job_id}/segments/add", response_model=TranscriptionResponse)
@route_handler("add_segment", TranscriptionResponse)
async def add_segment(
    job_id: JobID,
    segment: SegmentUpdate,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
) -> TranscriptionResponse:
    """Add a new segment to a transcription.
    
    Args:
        job_id: Job ID to add segment to
        segment: Segment to add
        job_manager: Job manager service
        transcription: Transcription service
        
    Returns:
        Updated transcription response
        
    Raises:
        ResourceNotFoundError: If job not found
        ValidationError: If segment data invalid
        TranscriboError: If operation fails
    """
    try:
        # Get job
        job = await job_manager.get_job_status(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(cast(FileID, job.get('file_id')))
        
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
        await transcription.save_transcription(cast(FileID, job.get('file_id')), transcription_data)
        
        return TranscriptionResponse(status="success", transcription=transcription_data)
        
    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "add_segment",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "segment": segment.dict()
            }
        }
        raise TranscriboError("Failed to add segment", details=error_context)

@router.delete("/{job_id}/segments/{segment_index}", response_model=TranscriptionResponse)
@route_handler("delete_segment", TranscriptionResponse)
async def delete_segment(
    job_id: JobID,
    segment_index: int,
    job_manager: JobManager = Depends(JobManagerDep),
    transcription: TranscriptionService = Depends(TranscriptionDep)
) -> TranscriptionResponse:
    """Delete a segment from a transcription.
    
    Args:
        job_id: Job ID to delete segment from
        segment_index: Index of segment to delete
        job_manager: Job manager service
        transcription: Transcription service
        
    Returns:
        Updated transcription response
        
    Raises:
        ResourceNotFoundError: If job not found
        ValidationError: If segment index invalid
        TranscriboError: If operation fails
    """
    try:
        # Get job
        job = await job_manager.get_job_status(job_id)
        
        # Get transcription
        transcription_data = await transcription.get_transcription(cast(FileID, job.get('file_id')))
        
        # Delete segment
        segments = transcription_data.get("segments", [])
        if segment_index < 0 or segment_index >= len(segments):
            error_context: ErrorContext = {
                "operation": "delete_segment",
                "resource_id": job_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": "Invalid segment index",
                    "index": segment_index,
                    "total_segments": len(segments)
                }
            }
            raise ValidationError("Invalid segment index", details=error_context)
        
        segments.pop(segment_index)
        transcription_data["segments"] = segments
        
        # Save updated transcription
        await transcription.save_transcription(cast(FileID, job.get('file_id')), transcription_data)
        
        return TranscriptionResponse(status="success", transcription=transcription_data)
        
    except (ResourceNotFoundError, ValidationError):
        raise
    except Exception as e:
        error_context: ErrorContext = {
            "operation": "delete_segment",
            "resource_id": job_id,
            "timestamp": datetime.utcnow(),
            "details": {
                "error": str(e),
                "segment_index": segment_index
            }
        }
        raise TranscriboError("Failed to delete segment", details=error_context)
