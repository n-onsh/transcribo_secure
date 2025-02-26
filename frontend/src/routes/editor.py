"""Editor routes."""

import httpx
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from ..config import settings

router = APIRouter()
templates = Jinja2Templates(directory="frontend/src/templates")

@router.get("/editor/{job_id}/download")
async def download_editor(request: Request, job_id: str):
    """Download standalone editor."""
    try:
        # Get downloadable editor from backend
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.api_url}/api/editor/{job_id}/download")
            if response.status_code != 200:
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "message": "Failed to download editor",
                        "details": response.text
                    }
                )
            
            # Return the downloadable HTML
            return HTMLResponse(
                content=response.text,
                headers={
                    "Content-Disposition": f"attachment; filename=editor_{job_id}.html"
                }
            )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error downloading editor",
                "details": str(e)
            }
        )

@router.get("/editor/{job_id}", response_class=HTMLResponse)
async def editor_page(request: Request, job_id: str):
    """Editor page."""
    try:
        # Get editor data from backend
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.api_url}/api/editor/{job_id}")
            if response.status_code != 200:
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "message": "Failed to load editor",
                        "details": response.text
                    }
                )
            
            data = response.json()
        
        # Render editor template
        return templates.TemplateResponse(
            "editor.html",
            {
                "request": request,
                "job_id": job_id,
                "transcription": data["transcription"],
                "media_url": data["media_url"],
                "job": data["job"]
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading editor",
                "details": str(e)
            }
        )

@router.get("/editor/{job_id}/viewer", response_class=HTMLResponse)
async def viewer_page(request: Request, job_id: str):
    """Viewer page."""
    try:
        # Get viewer data from backend
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{settings.api_url}/api/editor/{job_id}")
            if response.status_code != 200:
                return templates.TemplateResponse(
                    "error.html",
                    {
                        "request": request,
                        "message": "Failed to load viewer",
                        "details": response.text
                    }
                )
            
            data = response.json()
        
        # Render viewer template
        return templates.TemplateResponse(
            "viewer.html",
            {
                "request": request,
                "job_id": job_id,
                "transcription": data["transcription"],
                "media_url": data["media_url"],
                "job": data["job"]
            }
        )
    except Exception as e:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "message": "Error loading viewer",
                "details": str(e)
            }
        )
