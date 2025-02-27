"""Service provider for transcriber service."""

import os
from typing import Dict, Optional
from .transcription import TranscriptionService
from .backend import BackendClient
from ..utils.logging import log_info, log_error

class TranscriberServiceProvider:
    """Provider for transcriber services."""

    def __init__(self):
        """Initialize service provider."""
        self.settings = None
        self.backend = None
        self.transcription = None
        self.initialized = False

    async def initialize(self):
        """Initialize services."""
        if self.initialized:
            return

        try:
            # Load settings
            self.settings = self._load_settings()
            log_info("Settings loaded")

            # Initialize backend client
            self.backend = BackendClient(self.settings['backend_url'])
            log_info("Backend client initialized")

            # Initialize transcription service
            self.transcription = TranscriptionService(self.settings)
            await self.transcription.initialize()
            log_info("Transcription service initialized")

            self.initialized = True
            log_info("Service provider initialization complete")

        except Exception as e:
            log_error(f"Failed to initialize service provider: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up services."""
        try:
            if self.transcription:
                await self.transcription.cleanup()
                log_info("Transcription service cleaned up")

            if self.backend:
                await self.backend.close()
                log_info("Backend client closed")

            self.initialized = False
            log_info("Service provider cleanup complete")

        except Exception as e:
            log_error(f"Error during service provider cleanup: {str(e)}")
            raise

    def _load_settings(self) -> Dict:
        """Load settings from environment."""
        return {
            'device': os.getenv('DEVICE', 'cpu'),
            'batch_size': int(os.getenv('BATCH_SIZE', '32')),
            'backend_url': os.getenv('BACKEND_API_URL', 'http://backend:8080/api/v1'),
            'model_path': os.getenv('MODEL_PATH', '/models'),
            'cache_dir': os.getenv('CACHE_DIR', '/cache'),
            'max_concurrent_jobs': int(os.getenv('MAX_CONCURRENT_JOBS', '2')),
            'chunk_size': int(os.getenv('CHUNK_SIZE', '30')),  # seconds
            'max_retries': int(os.getenv('MAX_RETRIES', '3')),
            'retry_delay': float(os.getenv('RETRY_DELAY', '1.0')),
            'supported_languages': os.getenv('SUPPORTED_LANGUAGES', 'de,en,fr,it').split(','),
            'default_language': os.getenv('DEFAULT_LANGUAGE', 'de')
        }
