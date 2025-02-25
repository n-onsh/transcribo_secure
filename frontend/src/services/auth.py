from msal import PublicClientApplication, ConfidentialClientApplication
import os
from typing import Optional, Dict, List
import logging
from nicegui import ui, app
import httpx

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, client_id: str, tenant_id: str, redirect_uri: str):
        """Initialize MSAL authentication"""
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.redirect_uri = redirect_uri
        
        if not all([self.client_id, self.tenant_id, self.redirect_uri]):
            raise ValueError("Missing required Azure AD configuration")
        
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
        
        # Store token in app storage
        self.token_key = "azure_token"

    async def login(self):
        """Initiate login flow"""
        try:
            # Get auth URL
            auth_url = self.msal_app.get_authorization_request_url(
                scopes=self.scopes,
                redirect_uri=f"{self.redirect_uri}/auth",
                response_type="code"
            )
            
            # Redirect to Azure AD login
            return auth_url
            
        except Exception as e:
            logger.error(f"Login failed: {str(e)}")
            raise

    async def handle_callback(self, code: str) -> Dict:
        """Handle auth callback and get token"""
        try:
            # Get token from code
            result = await self.msal_app.acquire_token_by_authorization_code(
                code=code,
                scopes=self.scopes,
                redirect_uri=f"{self.redirect_uri}/auth"
            )
            
            if "error" in result:
                raise Exception(result.get("error_description", "Authentication failed"))
            
            # Store token
            app.storage.user[self.token_key] = result
            
            # Get user info
            user_info = await self.get_user_info(result["access_token"])
            
            return user_info
            
        except Exception as e:
            logger.error(f"Auth callback failed: {str(e)}")
            raise

    async def get_token(self) -> Optional[str]:
        """Get current access token, refresh if needed"""
        try:
            token_data = app.storage.user.get(self.token_key)
            
            if not token_data:
                return None
            
            # Check if token needs refresh
            if self.msal_app.get_accounts():
                if self.msal_app.acquire_token_silent(
                    self.scopes,
                    account=self.msal_app.get_accounts()[0]
                ):
                    # Token still valid
                    return token_data["access_token"]
            
            # Token expired, try to refresh
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                result = await self.msal_app.acquire_token_by_refresh_token(
                    refresh_token,
                    scopes=self.scopes
                )
                
                if "error" not in result:
                    app.storage.user[self.token_key] = result
                    return result["access_token"]
            
            # Token refresh failed
            return None
            
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            return None

    async def get_user_info(self, token: str) -> Dict:
        """Get user info from Microsoft Graph"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token}"}
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get user info: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up resources"""
        try:
            # Clear stored token
            if self.token_key in app.storage.user:
                del app.storage.user[self.token_key]
            
            # Clear MSAL cache
            for account in self.msal_app.get_accounts():
                self.msal_app.remove_account(account)
            
            # Clear MSAL app
            self.msal_app = None
            
            logger.info("Auth service cleaned up")
            
        except Exception as e:
            logger.error(f"Auth cleanup failed: {str(e)}")
            raise

    def logout(self):
        """Clear stored token and logout"""
        try:
            # Clear stored token
            if self.token_key in app.storage.user:
                del app.storage.user[self.token_key]
            
            # Clear MSAL cache
            for account in self.msal_app.get_accounts():
                self.msal_app.remove_account(account)
            
            # Return home path for redirect
            return "/"
            
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            raise

    async def ensure_authenticated(self):
        """Ensure user is authenticated"""
        token = await self.get_token()
        if not token:
            await self.login()
            return False
        return True
