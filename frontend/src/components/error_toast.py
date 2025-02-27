"""Error toast notification component."""

from typing import Dict, List, Optional, Any
import json
from datetime import datetime
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="src/templates")

class ErrorToastComponent:
    """Toast notification component for errors."""
    
    def __init__(self):
        """Initialize component."""
        self.toast_levels = {
            "info": {
                "icon": "bi-info-circle",
                "class": "bg-info"
            },
            "warning": {
                "icon": "bi-exclamation-triangle",
                "class": "bg-warning"
            },
            "error": {
                "icon": "bi-exclamation-circle",
                "class": "bg-danger"
            },
            "critical": {
                "icon": "bi-x-octagon",
                "class": "bg-danger"
            }
        }
        
        self.toast_config = {
            "autohide": True,
            "delay": 5000,
            "animation": True
        }
    
    def format_time(self, timestamp: datetime) -> str:
        """Format timestamp for display.
        
        Args:
            timestamp: Datetime to format
            
        Returns:
            Formatted time string
        """
        now = datetime.utcnow()
        delta = now - timestamp
        
        if delta.days > 0:
            return timestamp.strftime("%Y-%m-%d %H:%M")
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "Just now"
    
    def prepare_error(self, error: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare error data for display.
        
        Args:
            error: Raw error data
            
        Returns:
            Prepared error data
        """
        # Generate unique ID if not present
        if "id" not in error:
            error["id"] = f"error-{datetime.utcnow().timestamp()}"
        
        # Format timestamp
        if "timestamp" in error:
            error["timestamp"] = self.format_time(error["timestamp"])
        
        # Set default title based on severity
        if "title" not in error:
            error["title"] = error.get("severity", "error").title()
        
        # Ensure required fields exist
        error.setdefault("severity", "error")
        error.setdefault("message", "An error occurred")
        error.setdefault("details", {})
        error.setdefault("recovery_suggestions", [])
        error.setdefault("is_retryable", False)
        
        return error
    
    async def render(
        self,
        request: Request,
        errors: Optional[List[Dict[str, Any]]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """Render toast component.
        
        Args:
            request: FastAPI request
            errors: List of error objects to display
            config: Optional toast configuration overrides
            
        Returns:
            Rendered component
        """
        # Prepare errors for display
        prepared_errors = [
            self.prepare_error(error)
            for error in (errors or [])
        ]
        
        # Merge config with defaults
        toast_config = self.toast_config.copy()
        if config:
            toast_config.update(config)
        
        return templates.TemplateResponse(
            "components/error_toast.html",
            {
                "request": request,
                "errors": prepared_errors,
                "toast_levels": self.toast_levels,
                "toast_config": json.dumps(toast_config),
                "format_time": self.format_time
            }
        )
    
    def create_error(
        self,
        message: str,
        severity: str = "error",
        title: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        recovery_suggestions: Optional[List[Dict[str, Any]]] = None,
        is_retryable: bool = False,
        operation: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create an error object.
        
        Args:
            message: Error message
            severity: Error severity level
            title: Optional error title
            details: Optional error details
            recovery_suggestions: Optional recovery suggestions
            is_retryable: Whether the operation can be retried
            operation: Optional operation identifier for retry
            
        Returns:
            Error object
        """
        error = {
            "message": message,
            "severity": severity,
            "timestamp": datetime.utcnow(),
            "details": details or {},
            "recovery_suggestions": recovery_suggestions or [],
            "is_retryable": is_retryable
        }
        
        if title:
            error["title"] = title
            
        if operation and is_retryable:
            error["operation"] = operation
        
        return self.prepare_error(error)
    
    def create_validation_error(
        self,
        field: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a validation error object.
        
        Args:
            field: Field that failed validation
            message: Error message
            details: Optional error details
            
        Returns:
            Validation error object
        """
        return self.create_error(
            message=message,
            severity="warning",
            title="Validation Error",
            details={
                "field": field,
                **(details or {})
            },
            recovery_suggestions=[{
                "action": "Check Input",
                "description": f"Verify the {field} field meets requirements"
            }]
        )
    
    def create_network_error(
        self,
        operation: str,
        message: str,
        is_retryable: bool = True
    ) -> Dict[str, Any]:
        """Create a network error object.
        
        Args:
            operation: Operation that failed
            message: Error message
            is_retryable: Whether the operation can be retried
            
        Returns:
            Network error object
        """
        return self.create_error(
            message=message,
            severity="error",
            title="Network Error",
            details={
                "operation": operation
            },
            recovery_suggestions=[{
                "action": "Check Connection",
                "description": "Verify your internet connection is working"
            }],
            is_retryable=is_retryable,
            operation=operation
        )
    
    def create_server_error(
        self,
        operation: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a server error object.
        
        Args:
            operation: Operation that failed
            message: Error message
            details: Optional error details
            
        Returns:
            Server error object
        """
        return self.create_error(
            message=message,
            severity="critical",
            title="Server Error",
            details={
                "operation": operation,
                **(details or {})
            },
            recovery_suggestions=[{
                "action": "Try Again Later",
                "description": "The server is experiencing issues"
            }]
        )
