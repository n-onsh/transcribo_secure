"""Service provider for frontend."""

import logging
from typing import Dict, Optional
from .auth import AuthService
from .api import ApiService

class FrontendServiceProvider:
    """Provider for frontend services."""

    def __init__(self):
        """Initialize service provider."""
        self.settings = None
        self.auth = None
        self.api = None
        self.initialized = False

    async def initialize(self):
        """Initialize services."""
        if self.initialized:
            return

        try:
            # Initialize settings
            self.settings = self._load_settings()
            logging.info("Settings loaded")

            # Initialize auth service
            self.auth = AuthService(self.settings)
            await self.auth.initialize()
            logging.info("Auth service initialized")

            # Initialize API client
            self.api = ApiService(self.settings)
            await self.api.initialize()
            logging.info("API service initialized")

            self.initialized = True
            logging.info("Service provider initialization complete")

        except Exception as e:
            logging.error(f"Failed to initialize service provider: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up services."""
        try:
            if self.api:
                await self.api.cleanup()
                logging.info("API service cleaned up")

            if self.auth:
                await self.auth.cleanup()
                logging.info("Auth service cleaned up")

            self.initialized = False
            logging.info("Service provider cleanup complete")

        except Exception as e:
            logging.error(f"Error during service provider cleanup: {str(e)}")
            raise

    def _load_settings(self) -> Dict:
        """Load settings from environment."""
        import os

        return {
            'backend_url': os.getenv('BACKEND_URL', 'http://backend:8000'),
            'auth_url': os.getenv('AUTH_URL', 'http://auth:8080'),
            'session_secret': os.getenv('SESSION_SECRET', 'default-secret'),
            'temp_dir': os.getenv('TEMP_DIR', '/tmp'),
            'upload_limit': int(os.getenv('UPLOAD_LIMIT', '104857600')),  # 100MB
            'allowed_extensions': os.getenv('ALLOWED_EXTENSIONS', '.mp3,.wav,.m4a').split(','),
            'request_timeout': int(os.getenv('REQUEST_TIMEOUT', '30')),  # 30 seconds
            'retry_limit': int(os.getenv('RETRY_LIMIT', '3'))
        }
