from nicegui import ui, app
from pathlib import Path
import asyncio
import logging
from datetime import datetime
from .services.api import APIService
import tempfile
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class TranscriboUI:
    def __init__(self):
        self.api = APIService()
        self.user_id = "test_user"  # We'll implement proper auth later
        self.refresh_interval = 5  # seconds

    async def _handle_upload(self, e):
        """Handle file upload"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(e.content.read())
                temp_path = Path(temp_file.name)

            try:
                # Upload to backend
                result = await self.api.upload_file(temp_path, self.user_id)
                ui.notify(f"File uploaded successfully")
                
                # Refresh job list
                await self._refresh_jobs()
                
            finally:
                # Cleanup temp file
                os.unlink(temp_path)
                
        except Exception as e:
            ui.notify(f"Upload failed: {str(e)}", type="error")
            logger.error(f"Upload error: {str(e)}")

    async def _refresh_jobs(self):
        """Refresh job list"""
        try:
            jobs = await self.api.get_user_jobs(self.user_id)
            
            # Clear existing content
            if hasattr(self, 'jobs_container'):
                self.jobs_container.clear()
            
            # Add jobs to UI
            with self.jobs_container:
                for job in jobs:
                    self._create_job_card(job)
                    
        except Exception as e:
            logger.error(f"Error refreshing jobs: {str(e)}")

    def _create_job_card(self, job):
        """Create a card for a job"""
        with ui.card().classes('w-full'):
            ui.label(f"File: {job['metadata'].get('original_filename', 'Unknown')}")
            ui.label(f"Status: {job['status']}")
            
            if job['status'] == 'completed':
                ui.button('View Results', on_click=lambda: self._show_results(job['job_id']))
            elif job['status'] == 'failed':
                ui.label(f"Error: {job.get('error_message', 'Unknown error')}")
                ui.button('Retry', on_click=lambda: self._retry_job(job['job_id']))
            
            if 'progress' in job:
                ui.linear_progress(value=job['progress']/100).classes('w-full')

    async def _show_results(self, job_id):
        """Show transcription results"""
        try:
            results = await self.api.get_transcription_result(job_id)
            
            # Create results dialog
            with ui.dialog() as dialog, ui.card():
                ui.label('Transcription Results')
                for segment in results.get('segments', []):
                    ui.label(f"{segment.get('speaker', 'Unknown')}: {segment.get('text', '')}")
                ui.button('Close', on_click=dialog.close)
            dialog.open()
            
        except Exception as e:
            ui.notify(f"Error showing results: {str(e)}", type="error")

    async def _retry_job(self, job_id):
        """Retry a failed job"""
        try:
            await self.api.retry_job(job_id)
            ui.notify("Job resubmitted")
            await self._refresh_jobs()
        except Exception as e:
            ui.notify(f"Error retrying job: {str(e)}", type="error")

    async def _auto_refresh(self):
        """Automatically refresh job list"""
        while True:
            await asyncio.sleep(self.refresh_interval)
            await self._refresh_jobs()

    def create_ui(self):
        """Create the main UI"""
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
            
            # Start auto-refresh task
            asyncio.create_task(self._auto_refresh())

@ui.page('/')
def main_page():
    app_ui = TranscriboUI()
    app_ui.create_ui()

if __name__ == '__main__':
    ui.run(
        title='TranscriboZH',
        port=8080,
        reload=False
    )