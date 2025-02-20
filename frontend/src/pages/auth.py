from nicegui import ui
from ..services.auth import AuthService
import logging

logger = logging.getLogger(__name__)

@ui.page("/auth")
async def auth_callback():
    """Handle Azure AD authentication callback"""
    try:
        # Get auth code from query params
        code = ui.query_parameters.get("code")
        if not code:
            ui.notify("Authentication failed: No code provided", type="error")
            ui.open("/")
            return
        
        # Handle authentication
        auth_service = AuthService()
        user_info = await auth_service.handle_callback(code)
        
        # Show success message
        ui.notify(f"Welcome, {user_info.get('displayName', 'User')}!")
        
        # Redirect to home
        ui.open("/")
        
    except Exception as e:
        logger.error(f"Authentication callback failed: {str(e)}")
        ui.notify("Authentication failed", type="error")
        ui.open("/")

@ui.page("/logout")
async def logout():
    """Handle logout"""
    try:
        auth_service = AuthService()
        auth_service.logout()
        ui.notify("Successfully logged out")
    except Exception as e:
        logger.error(f"Logout failed: {str(e)}")
        ui.notify("Logout failed", type="error")
    finally:
        ui.open("/")
