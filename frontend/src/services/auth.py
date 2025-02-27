"""Authentication service."""

from msal import PublicClientApplication, ConfidentialClientApplication
import os
from typing import Optional, Dict, List, Tuple
import logging
from datetime import datetime, timedelta
from nicegui import ui, app
import httpx

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, client_id: str, tenant_id: str, redirect_uri: str, api_url: str):
        """Initialize MSAL authentication.
        
        Args:
            client_id: Azure AD client ID
            tenant_id: Azure AD tenant ID
            redirect_uri: OAuth redirect URI
            api_url: Backend API URL
        """
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.redirect_uri = redirect_uri
        self.api_url = api_url
        
        if not all([self.client_id, self.tenant_id, self.redirect_uri, self.api_url]):
            raise ValueError("Missing required configuration")
        
        # Initialize MSAL client
        self.msal_app = PublicClientApplication(
            client_id=self.client_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
        
        # Define required scopes
        self.scopes = [
            "User.Read",
            "Group.Read.All",
            f"api://{self.client_id}/access_as_user"
        ]
        
        # In-memory token storage
        self._current_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def login(self) -> str:
        """Initiate login flow.
        
        Returns:
            Azure AD authorization URL
        """
        try:
            # Get auth URL
            auth_url = self.msal_app.get_authorization_request_url(
                scopes=self.scopes,
                redirect_uri=f"{self.redirect_uri}/auth",
                response_type="code"
            )
            
            # Clear any existing tokens
            self._current_token = None
            self._refresh_token = None
            self._token_expiry = None
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    async def handle_callback(self, code: str) -> Dict:
        """Handle auth callback and get token.
        
        Args:
            code: Authorization code from Azure AD
            
        Returns:
            User info dictionary
        """
        try:
            # Get token from code - MSAL method is synchronous
            azure_result = self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.scopes,
                redirect_uri=f"{self.redirect_uri}/auth"
            )
            
            if "error" in azure_result:
                error_msg = azure_result.get("error_description", "Authentication failed")
                logger.error(f"Token acquisition failed: {error_msg}")
                raise Exception(error_msg)
            
            # Exchange Azure token for our session token
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/auth/exchange-token",
                    json={"azure_token": azure_result["access_token"]},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                session_data = response.json()
            
            # Store tokens in memory
            self._current_token = session_data["access_token"]
            self._refresh_token = session_data.get("refresh_token")
            self._token_expiry = datetime.utcnow() + timedelta(seconds=session_data["expires_in"])
            
            logger.info("Token successfully acquired and stored")
            
            # Get user info
            user_info = await self.get_user_info(self._current_token)
            
            return user_info
            
        except Exception as e:
            logger.error(f"Auth callback failed: {str(e)}")
            raise

    async def get_token(self) -> Optional[str]:
        """Get current access token, refresh if needed.
        
        Returns:
            Current access token if valid, None otherwise
        """
        try:
            # Check if we have a valid token
            if (
                self._current_token
                and self._token_expiry
                and datetime.utcnow() < self._token_expiry - timedelta(minutes=5)
            ):
                return self._current_token
            
            # Try to refresh token
            if self._refresh_token:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/auth/refresh",
                        json={"refresh_token": self._refresh_token},
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        session_data = response.json()
                        self._current_token = session_data["access_token"]
                        self._refresh_token = session_data.get("refresh_token")
                        self._token_expiry = datetime.utcnow() + timedelta(seconds=session_data["expires_in"])
                        logger.info("Token refreshed successfully")
                        return self._current_token
                    else:
                        logger.warning("Token refresh failed")
            
            logger.debug("No valid token available")
            return None
            
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            return None

    async def get_user_info(self, token: str) -> Dict:
        """Get user info from backend API.
        
        Args:
            token: Access token
            
        Returns:
            User info dictionary
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/auth/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up resources."""
        try:
            # Clear tokens
            self._current_token = None
            self._refresh_token = None
            self._token_expiry = None
            
            # Clear MSAL cache
            for account in self.msal_app.get_accounts():
                self.msal_app.remove_account(account)
            
            # Clear MSAL app
            self.msal_app = None
            
            logger.info("Auth service cleaned up")
            
        except Exception as e:
            logger.error(f"Auth cleanup failed: {str(e)}")
            raise

    async def logout(self) -> str:
        """Clear stored token and logout.
        
        Returns:
            Redirect path
        """
        try:
            if self._current_token:
                # Invalidate session on backend
                try:
                    async with httpx.AsyncClient() as client:
                        await client.post(
                            f"{self.api_url}/auth/logout",
                            headers={"Authorization": f"Bearer {self._current_token}"}
                        )
                except Exception as e:
                    logger.warning(f"Failed to invalidate session: {str(e)}")
            
            # Clear tokens
            self._current_token = None
            self._refresh_token = None
            self._token_expiry = None
            
            # Clear MSAL cache
            for account in self.msal_app.get_accounts():
                self.msal_app.remove_account(account)
            
            # Return home path for redirect
            return "/"
            
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise

    async def ensure_authenticated(self) -> bool:
        """Ensure user is authenticated.
        
        Returns:
            True if authenticated, False otherwise
        """
        token = await self.get_token()
        if not token:
            await self.login()
            return False
        return True

    async def get_active_sessions(self) -> List[Dict]:
        """Get list of active sessions.
        
        Returns:
            List of session info dictionaries
        """
        try:
            token = await self.get_token()
            if not token:
                return []
                
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/auth/sessions",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Failed to get active sessions: {str(e)}")
            return []
