from nicegui import ui
import asyncio
import httpx
import os

BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://backend-api:8080/api/v1")

class APIService:
    """Handles API interactions with the backend."""
    def __init__(self, user_id):
        self.user_id = user_id

    async def fetch_jobs(self):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_API_URL}/jobs/user/{self.user_id}")
                return response.json() if response.status_code == 200 else []
        except Exception as e:
            ui.notify(f"Failed to fetch jobs: {str(e)}", type="error")
            return []

    async def fetch_vocabulary(self):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_API_URL}/vocabulary/{self.user_id}")
                return response.json().get("vocabulary", "") if response.status_code == 200 else ""
        except Exception as e:
            ui.notify(f"Failed to fetch vocabulary: {str(e)}", type="error")
            return ""

    async def update_vocabulary(self, vocab_text):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(f"{BACKEND_API_URL}/vocabulary/{self.user_id}", json={"vocabulary": vocab_text})
                if response.status_code == 200:
                    ui.notify("Vocabulary updated successfully")
                else:
                    ui.notify("Failed to update vocabulary", type="error")
        except Exception as e:
            ui.notify(f"Error updating vocabulary: {str(e)}", type="error")


class JobUI:
    """Manages the job listing and interactions."""
    def __init__(self, api_service):
        self.api_service = api_service
        self.jobs_container = None
        self.refresh_interval = 5  # Polling interval in seconds

    async def start_polling(self):
        """Start background polling for jobs."""
        while True:
            await self.poll_jobs()
            await asyncio.sleep(self.refresh_interval)

    async def poll_jobs(self):
        """Fetch and update jobs from the backend."""
        jobs = await self.api_service.get_user_jobs("test_user")
        # Add logic to update the UI with jobs

    def create_ui(self):
        with ui.column().classes('w-full'):
            ui.label('Your Jobs')



class VocabularyUI:
    """Manages the vocabulary input and interactions."""
    def __init__(self, api_service):
        self.api_service = api_service
        self.vocab_input = None

    async def load_vocabulary(self):
        vocab_text = await self.api_service.fetch_vocabulary()
        self.vocab_input.set_value(vocab_text)

    def create_ui(self):
        with ui.expansion("Custom Vocabulary", icon="menu_book").classes("w-full"):
            self.vocab_input = ui.textarea(label="Vocabulary", placeholder="Enter custom words here...")
            ui.button("Save Vocabulary", on_click=lambda: self.api_service.update_vocabulary(self.vocab_input.value.strip()))


class TranscriboUI:
    """Main UI manager for the application."""
    def __init__(self):
        self.user_id = "test_user"  # Placeholder; this should eventually come from authentication
        self.api_service = APIService(self.user_id)  # Pass user_id explicitly
        self.job_ui = JobUI(self.api_service)  # Pass API service
        self.vocab_ui = VocabularyUI(self.api_service)  # Pass API service

    def create_ui(self):
        """Create the entire UI layout."""
        self.job_ui.create_ui()
        self.vocab_ui.create_ui()

        # Run background tasks on startup
        ui.on_startup(self.job_ui.start_polling)
        ui.on_startup(self.vocab_ui.load_vocabulary)



# Instantiate and create UI
app_ui = TranscriboUI()
app_ui.create_ui()

if __name__ == "__main__":
    app_ui = TranscriboUI()
    app_ui.create_ui()

    # Register startup tasks
    ui.run(
        on_startup=app_ui.vocab_ui.load_vocabulary,
        title="Transcribo Secure UI"
    )
