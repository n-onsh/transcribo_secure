from nicegui import ui
from nicegui import app as fastapi_app
import asyncio
import httpx
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend-api:8080/api/v1")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "5"))

class FileUploader:
    """Handles file upload functionality"""
    def __init__(self, api_client: httpx.AsyncClient, refresh_callback):
        self.api_client = api_client
        self.refresh_callback = refresh_callback
        
    async def handle_upload(self, e):
        """Handle file upload event"""
        try:
            files = {'file': (e.name, e.content.read())}
            response = await self.api_client.post(f"{BACKEND_API_URL}/files/", files=files)
            if response.status_code == 200:
                ui.notify(f"File {e.name} uploaded successfully")
                await self.refresh_callback()
            else:
                ui.notify(f"Upload failed: {response.text}", type='error')
        except Exception as e:
            ui.notify(f"Upload error: {str(e)}", type='error')

    def handle_reject(self, e):
        """Handle rejected files"""
        ui.notify("Invalid file. Only audio/video files under 12GB are allowed.", type='error')

class TranscriptionMonitor:
    """Monitors transcription jobs and updates UI"""
    def __init__(self, api_client: httpx.AsyncClient):
        self.api_client = api_client
        self.jobs = []
        self.known_errors = set()
        
    def format_time(self, seconds: float) -> str:
        return str(timedelta(seconds=round(seconds)))
        
    async def refresh_jobs(self):
        """Refresh job list from backend"""
        try:
            response = await self.api_client.get(f"{BACKEND_API_URL}/jobs/")
            if response.status_code == 200:
                self.jobs = response.json()
                await self.update_ui()
        except Exception as e:
            logger.error(f"Error refreshing jobs: {str(e)}")

    @ui.refreshable
    async def update_ui(self):
        """Update job status display"""
        with ui.card().classes('w-full p-4'):
            # Queue display
            for job in sorted(self.jobs, key=lambda x: (x['status'], -x['created_at'])):
                if job['status'] == 'processing':
                    progress = job.get('progress', 0)
                    ui.markdown(f"**{job['file_name']}**: Processing... {progress:.1f}%")
                    ui.linear_progress(value=progress/100).props('instant-feedback')
                elif job['status'] == 'pending':
                    estimated_time = self.format_time(job.get('estimated_time', 0))
                    ui.markdown(f"**{job['file_name']}**: Queued. Estimated wait: {estimated_time}")
                ui.separator()

            # Results display
            completed_jobs = [j for j in self.jobs if j['status'] == 'completed']
            for job in completed_jobs:
                ui.markdown(f"**{job['file_name']}**")
                with ui.row():
                    ui.button(
                        'Download Editor',
                        on_click=lambda j=job: self.download_editor(j['job_id'])
                    ).props('no-caps')
                    ui.button(
                        'Open Editor',
                        on_click=lambda j=job: self.open_editor(j['job_id'])
                    ).props('no-caps')
                    ui.button(
                        'Download SRT',
                        on_click=lambda j=job: self.download_srt(j['job_id'])
                    ).props('no-caps')
                    ui.button(
                        'Remove',
                        on_click=lambda j=job: self.remove_job(j['job_id']),
                        color='red-5'
                    ).props('no-caps')
                ui.separator()

    async def download_editor(self, job_id: str):
        """Download editor HTML"""
        try:
            response = await self.api_client.get(f"{BACKEND_API_URL}/jobs/{job_id}/viewer")
            if response.status_code == 200:
                ui.download(content=response.text, filename=f"editor_{job_id}.html")
            else:
                ui.notify("Failed to download editor", type='error')
        except Exception as e:
            ui.notify(f"Download error: {str(e)}", type='error')

    async def open_editor(self, job_id: str):
        """Open editor in new tab"""
        try:
            ui.open(f"/editor/{job_id}", new_tab=True)
        except Exception as e:
            ui.notify(f"Error opening editor: {str(e)}", type='error')

    async def download_srt(self, job_id: str):
        """Download SRT file"""
        try:
            response = await self.api_client.get(f"{BACKEND_API_URL}/jobs/{job_id}/export/srt")
            if response.status_code == 200:
                ui.download(content=response.json()['srt'], filename=f"transcript_{job_id}.srt")
            else:
                ui.notify("Failed to download SRT", type='error')
        except Exception as e:
            ui.notify(f"Download error: {str(e)}", type='error')

    async def remove_job(self, job_id: str):
        """Remove job and associated files"""
        try:
            response = await self.api_client.delete(f"{BACKEND_API_URL}/jobs/{job_id}")
            if response.status_code == 200:
                ui.notify("Job removed successfully")
                await self.refresh_jobs()
            else:
                ui.notify("Failed to remove job", type='error')
        except Exception as e:
            ui.notify(f"Error removing job: {str(e)}", type='error')

class VocabularyManager:
    """Manages custom vocabulary"""
    def __init__(self, api_client: httpx.AsyncClient):
        self.api_client = api_client
        self.vocabulary = set()

    async def load_vocabulary(self):
        """Load vocabulary from backend"""
        try:
            response = await self.api_client.get(f"{BACKEND_API_URL}/vocabulary")
            if response.status_code == 200:
                self.vocabulary = set(response.json()['words'])
                if hasattr(self, 'textarea'):
                    self.textarea.value = '\n'.join(sorted(self.vocabulary))
        except Exception as e:
            logger.error(f"Error loading vocabulary: {str(e)}")

    async def save_vocabulary(self, text: str):
        """Save vocabulary to backend"""
        try:
            words = {word.strip() for word in text.split('\n') if word.strip()}
            response = await self.api_client.post(
                f"{BACKEND_API_URL}/vocabulary",
                json={'words': list(words)}
            )
            if response.status_code == 200:
                ui.notify("Vocabulary saved")
                self.vocabulary = words
            else:
                ui.notify("Failed to save vocabulary", type='error')
        except Exception as e:
            ui.notify(f"Error saving vocabulary: {str(e)}", type='error')

class TranscriboUI:
    """Main UI application"""
    def __init__(self):
        self.api_client = httpx.AsyncClient()
        self.monitor = TranscriptionMonitor(self.api_client)
        self.vocabulary = VocabularyManager(self.api_client)
        self.uploader = FileUploader(self.api_client, self.monitor.refresh_jobs)

    async def create_ui(self):
        """Create main UI layout"""
        # Header
        with ui.header(elevated=True).style("background-color: #0070b4;").classes("q-pa-xs-xs"):
            ui.image(str(Path(__file__).parent / "data" / "banner.png")).style(
                "height: 90px; width: 443px;"
            )

        # Main content
        with ui.row():
            # Left column
            with ui.column():
                with ui.card().classes("border p-4"):
                    # File upload
                    with ui.card().style("width: min(40vw, 400px)"):
                        upload = ui.upload(
                            multiple=True,
                            on_upload=self.uploader.handle_upload,
                            on_rejected=self.uploader.handle_reject,
                            label="Select Files",
                            auto_upload=True,
                            max_file_size=12_000_000_000,
                            max_files=100,
                        ).props('accept="video/*, audio/*, .zip"').classes("w-full")

                    # Vocabulary section
                    with ui.expansion("Vocabulary", icon="menu_book").classes("w-full"):
                        self.vocabulary.textarea = ui.textarea(
                            label="Vocabulary",
                            placeholder="Zürich\nUster\nUitikon",
                            on_change=lambda e: self.vocabulary.save_vocabulary(e.value)
                        ).classes("w-full")

                    # Help section
                    with ui.expansion("Information", icon="help_outline").classes("w-full"):
                        ui.label("This application was developed by the Statistical Office of Canton Zurich.")

                    ui.button(
                        "Open Help",
                        on_click=lambda: ui.open('/help', new_tab=True)
                    ).props("no-caps")

            # Right column - Job monitor
            await self.monitor.update_ui()

        # Start background tasks
        asyncio.create_task(self._poll_jobs())
        await self.vocabulary.load_vocabulary()

    async def _poll_jobs(self):
        """Background task to poll for job updates"""
        while True:
            await self.monitor.refresh_jobs()
            await asyncio.sleep(REFRESH_INTERVAL)

async def startup():
    """Application startup handler"""
    app_ui = TranscriboUI()
    await app_ui.create_ui()

# Export the FastAPI app instance
app = fastapi_app

# Register startup handler
app.on_startup(startup)

# Export the FastAPI app instance
app = fastapi_app

# Register startup handler
app.on_startup(startup)

# Modified main guard to work with multiprocessing
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="TranscriboZH",
        host="0.0.0.0",
        port=8501,
        reload=False
    )