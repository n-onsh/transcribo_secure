from nicegui import ui, app
import os
import logging
import time
from src.services.auth import AuthService
from src.services.api import APIService
from src.utils.metrics import (
    http_requests_total,
    http_request_duration,
    file_upload_total,
    job_status_total
)
from src.utils import setup_telemetry
from pathlib import Path
import asyncio

# Initialize OpenTelemetry
setup_telemetry(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
auth_service = AuthService()
api_service = APIService()

async def check_auth():
    """Check authentication before each page load"""
    try:
        token = await auth_service.get_token()
        if not token:
            auth_url = await auth_service.login()
            ui.open(auth_url)
            return False
        return True
    except Exception as e:
        logger.error(f"Authentication check failed: {str(e)}")
        return False

def track_request(endpoint):
    """Decorator to track request metrics"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                http_requests_total.add(1, {"method": "GET", "endpoint": endpoint, "status": "success"})
                http_request_duration.record(duration, {"method": "GET", "endpoint": endpoint})
                return result
            except Exception as e:
                duration = time.time() - start_time
                http_requests_total.add(1, {"method": "GET", "endpoint": endpoint, "status": "error"})
                http_request_duration.record(duration, {"method": "GET", "endpoint": endpoint})
                raise
        return wrapper
    return decorator

@ui.page('/auth')
@track_request('/auth')
async def auth_callback():
    """Handle Azure AD auth callback"""
    try:
        code = ui.query.get('code')
        if code:
            await auth_service.handle_callback(code)
            ui.open('/')
    except Exception as e:
        logger.error(f"Auth callback failed: {str(e)}")
        ui.notify("Authentication failed", type="error")
        ui.open('/')

@ui.page('/logout')
def logout():
    """Handle logout"""
    try:
        redirect_path = auth_service.logout()
        ui.open(redirect_path)
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        ui.notify("Logout failed", type="error")

@ui.page('/')
@track_request('/')
async def main_page():
    """Main application page with authentication"""
    try:
        if not await check_auth():
            return
        
        with ui.column():
            # Header with user info and logout
            with ui.header(elevated=True).style("background-color: #0070b4;").classes("q-pa-xs-xs"):
                with ui.row().classes("w-full items-center justify-between"):
                    # Logo
                    ui.image(str(Path(__file__).parent / "data" / "banner.png")).style(
                        "height: 90px; width: 443px;"
                    )
                    
                    # User menu
                    with ui.button(icon="account_circle").props('flat'):
                        with ui.menu() as menu:
                            ui.menu_item('Logout', on_click=lambda: ui.open('/logout'))

            # Main content
            with ui.row():
                # Left column
                with ui.column():
                    with ui.card().classes("border p-4"):
                        # File upload
                        with ui.card().style("width: min(40vw, 400px)"):
                            upload = ui.upload(
                                multiple=True,
                                on_upload=handle_upload,
                                on_rejected=handle_reject,
                                label="Select Files",
                                auto_upload=True,
                                max_file_size=12_000_000_000,
                                max_files=100,
                            ).props('accept="video/*, audio/*, .zip"').classes("w-full")

                        # Vocabulary section
                        with ui.expansion("Vocabulary", icon="menu_book").classes("w-full"):
                            vocabulary = ui.textarea(
                                label="Vocabulary",
                                placeholder="Zürich\nUster\nUitikon",
                                on_change=handle_vocabulary_change
                            ).classes("w-full")
                            
                            try:
                                # Load vocabulary
                                words = await api_service.get_vocabulary()
                                if words:
                                    vocabulary.value = "\n".join(words)
                            except Exception as e:
                                logger.error(f"Failed to load vocabulary: {str(e)}")
                                ui.notify("Failed to load vocabulary", type="error")

                        # Help section
                        with ui.expansion("Information", icon="help_outline").classes("w-full"):
                            ui.label("This application was developed by the Statistical Office of Canton Zurich.")

                        ui.button(
                            "Open Help",
                            on_click=lambda: ui.open('/help', new_tab=True)
                        ).props("no-caps")

                # Right column - Job monitor
                await update_jobs()

            # Start background tasks
            asyncio.create_task(poll_jobs())

    except Exception as e:
        logger.error(f"Error loading main page: {str(e)}")
        ui.notify("Error loading application", type="error")

async def handle_upload(e):
    """Handle file upload with authentication"""
    try:
        result = await api_service.upload_file(e.content, e.name)
        ui.notify(f"File {e.name} uploaded successfully")
        file_upload_total.add(1, {"status": "success"})
        await update_jobs()
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        file_upload_total.add(1, {"status": "error"})
        ui.notify("Upload failed", type="error")

def handle_reject(e):
    """Handle rejected files"""
    ui.notify("Invalid file. Only audio/video files under 12GB are allowed.", type="error")

async def handle_vocabulary_change(e):
    """Handle vocabulary changes"""
    try:
        words = [word.strip() for word in e.value.split("\n") if word.strip()]
        await api_service.save_vocabulary(words)
    except Exception as e:
        logger.error(f"Failed to save vocabulary: {str(e)}")
        ui.notify("Failed to save vocabulary", type="error")

@ui.refreshable
async def update_jobs():
    """Update job status display"""
    try:
        jobs = await api_service.get_jobs()
        
        # Update job status metrics
        status_counts = {}
        for job in jobs:
            status = job['status']
            status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            job_status_total.add(count, {"status": status})
        
        with ui.card().classes('w-full p-4'):
            # Queue display
            for job in sorted(jobs, key=lambda x: (x['status'], -x['created_at'])):
                if job['status'] == 'processing':
                    progress = job.get('progress', 0)
                    ui.markdown(f"**{job['file_name']}**: Processing... {progress:.1f}%")
                    ui.linear_progress(value=progress/100).props('instant-feedback')
                elif job['status'] == 'pending':
                    ui.markdown(f"**{job['file_name']}**: Queued")
                ui.separator()

            # Results display
            completed_jobs = [j for j in jobs if j['status'] == 'completed']
            for job in completed_jobs:
                ui.markdown(f"**{job['file_name']}**")
                with ui.row():
                    ui.button(
                        'Download Editor',
                        on_click=lambda j=job: download_editor(j['job_id'])
                    ).props('no-caps')
                    ui.button(
                        'Open Editor',
                        on_click=lambda j=job: ui.open(f'/editor/{j["job_id"]}', new_tab=True)
                    ).props('no-caps')
                    ui.button(
                        'Download SRT',
                        on_click=lambda j=job: download_srt(j['job_id'])
                    ).props('no-caps')
                ui.separator()
    except Exception as e:
        logger.error(f"Error updating jobs: {str(e)}")
        ui.notify("Failed to update jobs", type="error")

async def poll_jobs():
    """Background task to poll for job updates"""
    while True:
        try:
            await update_jobs()
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error polling jobs: {str(e)}")
            await asyncio.sleep(10)

async def download_editor(job_id: str):
    """Download editor HTML"""
    try:
        result = await api_service.get_transcription(job_id)
        ui.download(content=result["editor_html"], filename=f"editor_{job_id}.html")
    except Exception as e:
        logger.error(f"Failed to download editor: {str(e)}")
        ui.notify("Failed to download editor", type="error")

async def download_srt(job_id: str):
    """Download SRT file"""
    try:
        result = await api_service.get_transcription(job_id)
        ui.download(content=result["srt"], filename=f"transcript_{job_id}.srt")
    except Exception as e:
        logger.error(f"Failed to download SRT: {str(e)}")
        ui.notify("Failed to download SRT", type="error")

@ui.page('/health')
@track_request('/health')
async def health():
    """Health check endpoint"""
    return "OK"

@ui.page('/metrics')
async def metrics():
    """OpenTelemetry metrics endpoint"""
    # The OpenTelemetry collector will scrape metrics directly through the OTLP exporter
    # We don't need to implement a metrics endpoint ourselves
    return "OK"

# Start the application
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="TranscriboZH",
        host="0.0.0.0",
        port=int(os.getenv("FRONTEND_PORT", "8501")),
        storage_secret=os.getenv("STORAGE_SECRET"),
        reload=False
    )
