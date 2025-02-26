"""Service provider for transcriber."""

import logging
from typing import Dict, Optional, Type, TypeVar
from .transcription import TranscriptionService

T = TypeVar('T')

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
            # Initialize settings
            self.settings = self._load_settings()
            logging.info("Settings loaded")

            # Initialize backend client
            self.backend = await self._init_backend()
            logging.info("Backend client initialized")

            # Initialize transcription service
            self.transcription = TranscriptionService(self.settings)
            await self.transcription.initialize()
            logging.info("Transcription service initialized")

            self.initialized = True
            logging.info("Service provider initialization complete")

        except Exception as e:
            logging.error(f"Failed to initialize service provider: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up services."""
        try:
            if self.transcription:
                await self.transcription.cleanup()
                logging.info("Transcription service cleaned up")

            if self.backend:
                await self.backend.close()
                logging.info("Backend client closed")

            self.initialized = False
            logging.info("Service provider cleanup complete")

        except Exception as e:
            logging.error(f"Error during service provider cleanup: {str(e)}")
            raise

    def _load_settings(self) -> Dict:
        """Load settings from environment."""
        import os

        return {
            'device': os.getenv('DEVICE', 'cpu'),
            'batch_size': int(os.getenv('BATCH_SIZE', '32')),
            'poll_interval': float(os.getenv('POLL_INTERVAL', '5.0')),
            'backend_url': os.getenv('BACKEND_URL', 'http://backend:8000'),
            'model_path': os.getenv('MODEL_PATH', '/models'),
            'cache_dir': os.getenv('CACHE_DIR', '/cache'),
            'temp_dir': os.getenv('TEMP_DIR', '/tmp')
        }

    async def _init_backend(self):
        """Initialize backend client."""
        from httpx import AsyncClient
        return AsyncClient(base_url=self.settings['backend_url'])
