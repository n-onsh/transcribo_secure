from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional
from uuid import UUID
from ..models.job import Job, JobStatus, JobUpdate
from ..services.database import DatabaseService
from ..services.job_manager import JobManager
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Dependency to get services
async def get_services():
    db = DatabaseService()
    job_manager = JobManager(db)
    try:
        yield {"db": db, "job_manager": job_manager}
    finally:
        await db.close()

@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Get job status and details"""
    job = await services["db"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs/user/{user_id}", response_model=List[Job])
async def list_user_jobs(
    user_id: str,
    status: Optional[JobStatus] = None,
    limit: int = 100,
    offset: int = 0,
    services: dict = Depends(get_services)
):
    """List jobs for a user"""
    jobs = await services["db"].get_jobs_by_user(
        user_id,
        status=status,
        limit=limit,
        offset=offset
    )
    return jobs

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Cancel a pending or processing job"""
    job = await services["db"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=400,
            detail="Can only cancel pending or processing jobs"
        )
    
    update = JobUpdate(
        status=JobStatus.FAILED,
        error_message="Job cancelled by user"
    )
    updated_job = await services["job_manager"].update_job(job_id, update)
    return updated_job

@router.post("/jobs/{job_id}/status")
async def update_job_status(
    job_id: UUID,
    update: JobUpdate,
    background_tasks: BackgroundTasks,
    services: dict = Depends(get_services)
):
    """Update job status from transcriber service"""
    job = await services["db"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    try:
        updated_job = await services["job_manager"].update_job(job_id, update)
        
        # If job is completed successfully, schedule cleanup
        if update.status == JobStatus.COMPLETED:
            logger.info(f"Job {job_id} completed successfully")
            # Could add cleanup tasks here in the future
            
        # If job failed, log error
        elif update.status == JobStatus.FAILED:
            logger.error(f"Job {job_id} failed: {update.error_message}")
            
        return updated_job
        
    except Exception as e:
        logger.error(f"Error updating job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update job status: {str(e)}"
        )

@router.post("/jobs/retry/{job_id}")
async def retry_job(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Retry a failed job"""
    job = await services["db"].get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail="Can only retry failed jobs"
        )
    
    # Reset job status to pending
    update = JobUpdate(
        status=JobStatus.PENDING,
        error_message=None,
        progress=0.0
    )
    updated_job = await services["job_manager"].update_job(job_id, update)
    return updated_job

@router.get("/jobs/queue/status")
async def get_queue_status(
    services: dict = Depends(get_services)
):
    """Get current status of the job queue"""
    try:
        # Get counts for each status
        stats = await services["db"].get_job_stats()
        return {
            "queue_length": stats.get("pending", 0),
            "processing": stats.get("processing", 0),
            "completed": stats.get("completed", 0),
            "failed": stats.get("failed", 0),
            "total": sum(stats.values())
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get queue status"
        )