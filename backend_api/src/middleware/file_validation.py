from fastapi import HTTPException, Request
from typing import Callable
import magic
from ..config import get_settings

async def validate_file_middleware(request: Request, call_next: Callable):
    """Middleware to validate file uploads"""
    if request.method == "POST" and request.url.path.endswith("/files/"):
        settings = get_settings()
        
        # Check content length if available
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) > settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="File too large"
                )
        
        # Store original receive to use after validation
        original_receive = request.receive
        
        # Buffer to store the first chunk for content type detection
        first_chunk = None
        
        async def receive_wrapper():
            nonlocal first_chunk
            
            if first_chunk is None:
                first_chunk = await original_receive()
                
                # Only validate if it's the file part of multipart data
                if b'filename' in first_chunk.get('body', b''):
                    # Use python-magic to detect file type
                    mime = magic.Magic(mime=True)
                    detected_type = mime.from_buffer(first_chunk['body'])
                    
                    if detected_type not in settings.ALLOWED_FILE_TYPES:
                        raise HTTPException(
                            status_code=415,
                            detail=f"Unsupported file type: {detected_type}"
                        )
                
                return first_chunk
            return await original_receive()
        
        # Replace receive with our wrapper
        request._receive = receive_wrapper
    
    return await call_next(request)