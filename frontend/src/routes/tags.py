"""Tag management routes."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")

@router.get("/tags", response_class=HTMLResponse)
async def tags_page(request: Request):
    """Render tag management page."""
    return templates.TemplateResponse(
        "tags.html",
        {
            "request": request,
            "title": "Tag Management"
        }
    )
