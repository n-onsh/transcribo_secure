from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Optional
from uuid import UUID
from ..models.job import Job, JobStatus, JobType, JobUpdate
from ..services.storage import StorageService
from ..services.database import DatabaseService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

async def get_services():
    """Dependency to get database and storage services"""
    db = DatabaseService()
    storage = StorageService()
    try:
        yield {"db": db, "storage": storage}
    finally:
        await db.close()

@router.get("/jobs/next")
async def get_next_job(services: dict = Depends(get_services)):
    """Get the next available job for processing"""
    try:
        # Get oldest pending job
        jobs = await services["db"].get_pending_jobs(limit=1)
        if not jobs:
            raise HTTPException(status_code=404, detail="No jobs available")
            
        return jobs[0]
    except Exception as e:
        logger.error(f"Error getting next job: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/results")
async def upload_job_results(
    job_id: UUID,
    results: dict,
    services: dict = Depends(get_services)
):
    """Upload transcription results for a job"""
    try:
        # Get job
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Store results
        await services["storage"].store_file(
            file_id=job.file_id,
            file_data=results,
            file_name=f"{job_id}_results.json",
            file_type="output"
        )
        
        # Update job status
        await services["db"].update_job(
            job_id,
            JobUpdate(
                status=JobStatus.COMPLETED,
                metadata={"has_results": True}
            )
        )
        
        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"Error uploading results for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/input")
async def get_job_input(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Get input file for a job"""
    try:
        # Get job
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        # Get file
        file_data = await services["storage"].retrieve_file(
            file_id=job.file_id,
            file_name=job.metadata["original_filename"],
            file_type="input"
        )
        
        if not file_data:
            raise HTTPException(
                status_code=404,
                detail="Input file not found"
            )
        
        return file_data
        
    except Exception as e:
        logger.error(f"Error retrieving input for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/status")
async def update_job_status(
    job_id: UUID,
    update: JobUpdate,
    services: dict = Depends(get_services)
):
    """Update job status"""
    try:
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        updated_job = await services["db"].update_job(job_id, update)
        return updated_job
        
    except Exception as e:
        logger.error(f"Error updating status for job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/retry")
async def retry_job(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Reset a failed job to retry it"""
    try:
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        if job.status != JobStatus.FAILED:
            raise HTTPException(
                status_code=400,
                detail="Can only retry failed jobs"
            )
            
        updated_job = await services["db"].update_job(
            job_id,
            JobUpdate(
                status=JobStatus.PENDING,
                error_message=None,
                metadata={"retried": True}
            )
        )
        
        return updated_job
        
    except Exception as e:
        logger.error(f"Error retrying job {job_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))