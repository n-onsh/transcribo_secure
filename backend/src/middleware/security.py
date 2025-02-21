from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Dict

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    def __init__(self, app, **kwargs):
        super().__init__(app)
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
            
            # Enable strict CSP
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "  # Required for Swagger UI
                "style-src 'self' 'unsafe-inline'; "  # Required for Swagger UI
                "img-src 'self' data:; "
                "font-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'; "
                "block-all-mixed-content; "
                "upgrade-insecure-requests"
            ),
            
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
        """Get CORS configuration"""
        return {
            "allow_origins": [
                "http://localhost:3000",
                "https://localhost:3000"
            ],
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": [
                "Authorization",
                "Content-Type",
                "X-Request-ID",
                "X-Real-IP",
                "X-Forwarded-For"
            ],
            "expose_headers": [
                "Content-Length",
                "Content-Range",
                "X-Request-ID"
            ],
            "max_age": 3600
        }
