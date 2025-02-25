import logging
from typing import Dict, List, Optional, Protocol
from pydantic_settings import BaseSettings
from .auth import AuthService
from .api import APIService

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    """Frontend settings"""
    backend_api_url: str
    auth_client_id: str
    auth_tenant_id: str
    auth_redirect_uri: str
    storage_secret: str
    frontend_port: int = 8501

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"

class AuthServiceInterface(Protocol):
    """Interface for authentication service"""
    async def get_token(self) -> Optional[str]:
        """Get current auth token"""
        ...

    async def login(self) -> str:
        """Get login URL"""
        ...

    async def handle_callback(self, code: str) -> None:
        """Handle auth callback"""
        ...

    def logout(self) -> str:
        """Get logout URL"""
        ...

    async def cleanup(self) -> None:
        """Clean up resources"""
        ...

class APIServiceInterface(Protocol):
    """Interface for API service"""
    async def upload_file(self, content: bytes, name: str) -> Dict:
        """Upload file to backend"""
        ...

    async def get_jobs(self) -> List[Dict]:
        """Get list of jobs"""
        ...

    async def get_transcription(self, job_id: str) -> Dict:
        """Get transcription results"""
        ...

    async def get_vocabulary(self) -> List[str]:
        """Get vocabulary list"""
        ...

    async def save_vocabulary(self, words: List[str]) -> None:
        """Save vocabulary list"""
        ...

    async def cleanup(self) -> None:
        """Clean up resources"""
        ...

class FrontendServiceProvider:
    """Service provider for frontend container"""
    def __init__(self):
        """Initialize service provider"""
        self._settings = None
        self._auth = None
        self._api = None
        self._initialized = False
        logger.info("Frontend service provider initialized")

    async def initialize(self):
        """Initialize all services"""
        if self._initialized:
            return

        try:
            # Load settings
            self._settings = Settings()
            logger.info("Settings loaded")

            try:
                # Initialize auth service
                self._auth = AuthService(
                    client_id=self._settings.auth_client_id,
                    tenant_id=self._settings.auth_tenant_id,
                    redirect_uri=self._settings.auth_redirect_uri
                )
                logger.info("Auth service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize auth service: {str(e)}")
                raise

            try:
                # Initialize API service
                self._api = APIService(
                    base_url=self._settings.backend_api_url,
                    auth_service=self._auth
                )
                logger.info("API service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize API service: {str(e)}")
                await self._auth.cleanup()  # Clean up auth if API init fails
                raise

            self._initialized = True
            logger.info("All services initialized")

        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Clean up all services"""
        try:
            # Clean up services in reverse initialization order
            if self._api:
                try:
                    await self._api.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up API service: {str(e)}")

            if self._auth:
                try:
                    await self._auth.cleanup()
                except Exception as e:
                    logger.error(f"Error cleaning up auth service: {str(e)}")

            # Clear references
            self._api = None
            self._auth = None
            self._settings = None
            self._initialized = False
            logger.info("Services cleaned up")

        except Exception as e:
            logger.error(f"Error in cleanup process: {str(e)}")
            raise

    @property
    def settings(self) -> Settings:
        """Get settings"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._settings

    @property
    def auth(self) -> AuthServiceInterface:
        """Get auth service"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._auth

    @property
    def api(self) -> APIServiceInterface:
        """Get API service"""
        if not self._initialized:
            raise RuntimeError("Services not initialized")
        return self._api
