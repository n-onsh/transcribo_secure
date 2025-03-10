"""Frontend application."""

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app

from .components.upload import UploadComponent
from .routes import editor, tags, auth
from .utils import setup_metrics
from .utils.logging import setup_logging

# Configure logging
setup_logging()

# Create FastAPI app
app = FastAPI()

# Include routes
app.include_router(auth.router)
app.include_router(editor.router)
app.include_router(tags.router)

# Mount static files and assets
app.mount("/static", StaticFiles(directory="src/static"), name="static")
app.mount("/assets", StaticFiles(directory="backend/src/assets"), name="assets")

# Create metrics app
metrics_app = make_asgi_app()

# Mount metrics endpoint
app.mount("/metrics", metrics_app)

# Set up metrics
setup_metrics()

# Initialize templates
templates = Jinja2Templates(directory="src/templates")

# Initialize components
upload_component = UploadComponent()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page."""
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

@app.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    selected_language: str = None,
    errors: dict = None
):
    """Upload page."""
    return await upload_component.render(
        request=request,
        selected_language=selected_language,
        errors=errors
    )

@app.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request):
    """Jobs page."""
    return templates.TemplateResponse(
        "jobs.html",
        {"request": request}
    )

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    return templates.TemplateResponse(
        "settings.html",
        {"request": request}
    )

@app.get("/help", response_class=HTMLResponse)
async def help_page(request: Request):
    """Help page."""
    return templates.TemplateResponse(
        "help.html",
        {"request": request}
    )

@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    """About page."""
    return templates.TemplateResponse(
        "about.html",
        {"request": request}
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
