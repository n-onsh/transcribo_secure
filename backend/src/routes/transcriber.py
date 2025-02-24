from fastapi import APIRouter, HTTPException, status
from typing import Dict
from ..models.job import TranscriptionResponse
from ..services.interfaces import JobManagerInterface
from ..services.provider import service_provider
from ..utils.exceptions import ResourceNotFoundError, AuthorizationError
from ..utils.metrics import track_time, DB_OPERATION_DURATION

router = APIRouter(
    prefix="/transcriptions",
    tags=["transcriptions"]
)

@router.get(
    "/{job_id}",
    response_model=TranscriptionResponse,
    summary="Get Transcription",
    description="Get transcription result for a completed job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_transcription"})
async def get_transcription(
    job_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Get transcription result"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get transcription
        transcription = await job_manager.get_transcription(job_id, user_id)

        return TranscriptionResponse(
            job_id=job_id,
            text=transcription.text,
            segments=transcription.segments,
            speakers=transcription.speakers,
            language=transcription.language,
            duration=transcription.duration,
            word_count=transcription.word_count,
            confidence=transcription.confidence
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Transcription for job {job_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/{job_id}/status",
    response_model=Dict,
    summary="Get Transcription Status",
    description="Get current status of a transcription job"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_transcription_status"})
async def get_transcription_status(
    job_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Get transcription status"""
    try:
        # Get required services
        job_manager = service_provider.get(JobManagerInterface)
        if not job_manager:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get job
        job = await job_manager.get_job(job_id, user_id)
        if not job:
            raise ResourceNotFoundError("job", job_id)

        return {
            "status": job.status,
            "progress": job.progress,
            "error": job.error
        }

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
