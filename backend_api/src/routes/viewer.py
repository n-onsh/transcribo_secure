from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from ..services.viewer import ViewerService
from ..services.storage import StorageService
from ..services.database import DatabaseService
from typing import Optional
from uuid import UUID
import json
import base64

router = APIRouter(prefix="/api/v1")

async def get_services():
    """Dependency to get services"""
    db = DatabaseService()
    storage = StorageService()
    viewer = ViewerService()
    try:
        yield {"db": db, "storage": storage, "viewer": viewer}
    finally:
        await db.close()

@router.get("/jobs/{job_id}/viewer", response_class=HTMLResponse)
async def get_viewer(
    job_id: UUID,
    combine_speakers: bool = True,
    encode_media: bool = False,
    services: dict = Depends(get_services)
):
    """Get HTML viewer for job results"""
    try:
        # Get job results
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get transcription results
        result_data = await services["storage"].retrieve_file(
            file_id=job.file_id,
            file_name=f"{job_id}_results.json",
            file_type="output"
        )
        
        if not result_data:
            raise HTTPException(status_code=404, detail="Results not found")
        
        results = json.loads(result_data.decode())

        # Get media URL or content
        media_url = None
        if encode_media:
            media_data = await services["storage"].retrieve_file(
                file_id=job.file_id,
                file_name=job.metadata.get("original_filename"),
                file_type="input"
            )
            if media_data:
                media_url = f"data:video/mp4;base64,{base64.b64encode(media_data).decode()}"
        
        if not media_url:
            media_url = f"/api/v1/files/{job.file_id}/media"

        # Create viewer
        html_content = services["viewer"].create_viewer(
            segments=results["segments"],
            media_url=media_url,
            combine_speaker=combine_speakers,
            encode_base64=encode_media
        )

        return HTMLResponse(content=html_content)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/jobs/{job_id}/viewer/save")
async def save_viewer_changes(
    job_id: UUID,
    content: dict,
    services: dict = Depends(get_services)
):
    """Save changes made in the editor"""
    try:
        # Get job
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Store updated content
        await services["storage"].store_file(
            file_id=job.file_id,
            file_data=json.dumps(content).encode(),
            file_name=f"{job_id}_editor.html",
            file_type="output"
        )

        return {"status": "success"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/export/srt")
async def export_srt(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Export job results as SRT"""
    try:
        # Get job results
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        result_data = await services["storage"].retrieve_file(
            file_id=job.file_id,
            file_name=f"{job_id}_results.json",
            file_type="output"
        )
        
        if not result_data:
            raise HTTPException(status_code=404, detail="Results not found")
        
        results = json.loads(result_data.decode())

        # Create SRT content
        srt_content = services["viewer"].create_srt(results["segments"])

        return JSONResponse(content={"srt": srt_content})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs/{job_id}/export/text")
async def export_text(
    job_id: UUID,
    services: dict = Depends(get_services)
):
    """Export job results as plain text"""
    try:
        # Get job results
        job = await services["db"].get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        result_data = await services["storage"].retrieve_file(
            file_id=job.file_id,
            file_name=f"{job_id}_results.json",
            file_type="output"
        )
        
        if not result_data:
            raise HTTPException(status_code=404, detail="Results not found")
        
        results = json.loads(result_data.decode())

        # Create text content
        text_content = []
        current_speaker = None
        for segment in results["segments"]:
            if segment["speaker"] != current_speaker:
                if current_speaker is not None:
                    text_content.append("")
                text_content.append(f"{segment['speaker']} ({segment['start']:.1f}):")
                current_speaker = segment["speaker"]
            text_content.append(segment["text"])

        return JSONResponse(content={"text": "\n".join(text_content)})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))