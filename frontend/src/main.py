from nicegui import ui, app
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Import your unified APIService (must have upload, jobs, editor content, export, etc.)
from .services.api import APIService
# Import the Editor component
from .components.editor import Editor

load_dotenv()
logger = logging.getLogger(__name__)

#
# Instantiate the API service globally so we can share it
# among TranscriboUI and Editor.
#
api_service = APIService()
# Also instantiate a global Editor component with that same API service
editor = Editor(api_service)


class TranscriboUI:
    """
    Class-based UI approach from your original snippet, now extended with:
      - Export SRT/Text methods
      - "Open Editor" button for completed jobs
      - The ability to pass an existing APIService
    """
    def __init__(self, api_service: APIService = None):
        # Allow injection of an existing APIService or create a new one
        self.api = api_service or APIService()
        self.user_id = "test_user"  # We'll implement proper auth later
        self.refresh_interval = 5  # seconds

    async def _handle_upload(self, e):
        """Handle file upload (original approach, writing to temp file)."""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(e.content.read())
                temp_path = Path(temp_file.name)

            try:
                # Upload to backend
                result = await self.api.upload_file(temp_path, self.user_id)
                ui.notify("File uploaded successfully")

                # Refresh job list
                await self._refresh_jobs()

            finally:
                # Cleanup temp file
                os.unlink(temp_path)

        except Exception as exc:
            ui.notify(f"Upload failed: {str(exc)}", type="error")
            logger.error(f"Upload error: {str(exc)}")

    async def _refresh_jobs(self):
        """Refresh job list."""
        try:
            jobs = await self.api.get_user_jobs(self.user_id)

            # Clear existing content
            if hasattr(self, 'jobs_container'):
                self.jobs_container.clear()

            # Populate job cards
            with self.jobs_container:
                for job in jobs:
                    self._create_job_card(job)

        except Exception as exc:
            logger.error(f"Error refreshing jobs: {str(exc)}")

    def _create_job_card(self, job):
        """Create a card UI for a single job."""
        with ui.card().classes('w-full'):
            ui.label(f"File: {job['metadata'].get('original_filename', 'Unknown')}")
            ui.label(f"Status: {job['status']}")

            # If the job is complete, show "View Results", "Open Editor", and export buttons
            if job['status'] == 'completed':
                # Original "View Results" popup
                ui.button('View Results', on_click=lambda: self._show_results(job['job_id']))

                # === NEW: "Open Editor" button (navigates to the new /editor page)
                ui.button('Open Editor', on_click=lambda: ui.navigate(f'/editor/{job["job_id"]}'))

                # === NEW: Export SRT/Text
                ui.button(
                    'Export SRT',
                    on_click=lambda: ui.run_task(self._export_srt(job['job_id']))
                )
                ui.button(
                    'Export Text',
                    on_click=lambda: ui.run_task(self._export_text(job['job_id']))
                )

            elif job['status'] == 'failed':
                # Show error + retry
                ui.label(f"Error: {job.get('error_message', 'Unknown error')}")
                ui.button('Retry', on_click=lambda: ui.run_task(self._retry_job(job['job_id'])))

            # If there's a progress value, show a progress bar
            if 'progress' in job:
                ui.linear_progress(value=job['progress']/100).classes('w-full')

    async def _show_results(self, job_id):
        """
        Show transcription results in a dialog (original snippet).
        Even though you now have an Editor page, we keep this
        if you still want a quick “results” popup.
        """
        try:
            results = await self.api.get_transcription_result(job_id)

            # Create results dialog
            with ui.dialog() as dialog, ui.card():
                ui.label('Transcription Results')
                for segment in results.get('segments', []):
                    speaker = segment.get('speaker', 'Unknown')
                    text = segment.get('text', '')
                    ui.label(f"{speaker}: {text}")
                ui.button('Close', on_click=dialog.close)
            dialog.open()

        except Exception as exc:
            ui.notify(f"Error showing results: {str(exc)}", type="error")

    async def _retry_job(self, job_id):
        """Retry a failed job."""
        try:
            await self.api.retry_job(job_id)
            ui.notify("Job resubmitted")
            await self._refresh_jobs()
        except Exception as exc:
            ui.notify(f"Error retrying job: {str(exc)}", type="error")

    #
    # === NEW: Export methods (SRT, Text) ===
    #
    async def _export_srt(self, job_id: str):
        try:
            content = await self.api.export_srt(job_id)
            # Provide the user with a downloadable link
            ui.download(content, 'transcript.srt')
        except Exception as exc:
            ui.notify(f"Error exporting SRT: {str(exc)}", type="error")
            logger.error(f"Error exporting SRT: {str(exc)}")

    async def _export_text(self, job_id: str):
        try:
            content = await self.api.export_text(job_id)
            ui.download(content, 'transcript.txt')
        except Exception as exc:
            ui.notify(f"Error exporting text: {str(exc)}", type="error")
            logger.error(f"Error exporting text: {str(exc)}")

    async def _auto_refresh(self):
        """
        Automatically refresh job list every self.refresh_interval seconds.
        (Original snippet)
        """
        while True:
            await asyncio.sleep(self.refresh_interval)
            await self._refresh_jobs()

    def create_ui(self):
        """Create the main UI layout (on the '/' page)."""
        with ui.column().classes('w-full max-w-3xl mx-auto p-4'):
            # Header
            with ui.header().classes('w-full'):
                ui.label('TranscriboZH').classes('text-2xl')

            # Upload section
            with ui.card().classes('w-full'):
                ui.upload(
                    label='Upload Files',
                    multiple=True,
                    on_upload=self._handle_upload
                ).props('accept=audio/*,video/*').classes('w-full')

            # Jobs section
            ui.label('Your Jobs').classes('text-xl mt-4')
            self.jobs_container = ui.column().classes('w-full')

            # Kick off auto-refresh
            asyncio.create_task(self._auto_refresh())


#
# === PAGE ROUTES ===
#

# 1) MAIN PAGE: Instantiates and displays the TranscriboUI
@ui.page('/')
def main_page():
    # We create a single instance (global or local) of TranscriboUI
    # that references our global api_service. 
    # You could also define a global "ui_app = TranscriboUI(api_service)"
    # if you want just one instance for the entire app. This is fine too.
    app_ui = TranscriboUI(api_service=api_service)
    app_ui.create_ui()


# 2) EDITOR PAGE: Uses the Editor component for a given job_id
@ui.page('/editor/{job_id}')
async def editor_page(job_id: str):
    """
    The new Editor page for advanced editing.
    This calls Editor.show_editor(job_id), which:
      - loads the HTML from /jobs/{job_id}/viewer
      - injects it with keyboard shortcuts
      - sets up auto-save
    """
    await editor.show_editor(job_id)


#
# === RUN THE APP IF EXECUTED DIRECTLY ===
#
if __name__ == '__main__':
    ui.run(
        title='TranscriboZH',
        port=int(os.getenv('PORT', 8080)),
        reload=False
    )
