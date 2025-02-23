from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Dict
from ..config import get_settings

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
        settings = get_settings()
        
        # Build CSP header from settings
        csp_parts = []
        for directive, value in settings.CSP_DIRECTIVES.items():
            csp_parts.append(f"{directive} {value}")
        csp_header = "; ".join(csp_parts)
        
        self.security_headers = {
            # Prevent browsers from performing MIME type sniffing
            "X-Content-Type-Options": "nosniff",
            
            # Enable browser XSS filtering
            "X-XSS-Protection": "1; mode=block",
            
            # Prevent clickjacking attacks
            "X-Frame-Options": "DENY",
            
            # Control browser features and APIs
            "Permissions-Policy": (
                "accelerometer=(), "
                "camera=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "payment=(), "
                "usb=()"
            ),
            
            # Enable strict CSP from settings
            "Content-Security-Policy": csp_header + "; block-all-mixed-content; upgrade-insecure-requests",
            
            # Enable strict transport security
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            
            # Prevent information leakage
            "Server": "Transcribo",
            
            # Enable cross-origin isolation
            "Cross-Origin-Embedder-Policy": "require-corp",
            "Cross-Origin-Opener-Policy": "same-origin",
            "Cross-Origin-Resource-Policy": "same-origin"
        }

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""
        response = await call_next(request)
        
        # Add security headers
        for header_name, header_value in self.security_headers.items():
            response.headers[header_name] = header_value
            
        return response

class SecurityConfig:
    """Security configuration for FastAPI app"""
    
    @staticmethod
    def get_cors_config() -> Dict:
        """Get CORS configuration from settings"""
        settings = get_settings()
        return {
            "allow_origins": list(settings.CORS_ORIGINS),
            "allow_credentials": True,
            "allow_methods": list(settings.CORS_METHODS),
            "allow_headers": list(settings.CORS_HEADERS),
            "expose_headers": [
                "Content-Length",
                "Content-Range",
                "X-Request-ID"
            ],
            "max_age": settings.CORS_MAX_AGE
        }
