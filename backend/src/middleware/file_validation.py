"""
File validation middleware for FastAPI.

Validates uploaded files for:
1. MIME type
2. File size
3. Format validation
4. Security checks
"""
from fastapi import HTTPException, Request
from typing import Callable
import magic.magic as magic
from ..config import get_settings

async def validate_file_middleware(request: Request, call_next: Callable):
    """Middleware to validate file uploads"""
    if request.method == "POST" and request.url.path.endswith("/files/"):
        settings = get_settings()

        # Check if file was uploaded
        if not request.headers.get("content-type", "").startswith("multipart/form-data"):
            raise HTTPException(
                status_code=400,
                detail="No file uploaded. Please submit a file using multipart/form-data."
            )
        
        # Check content length if available
        content_length = request.headers.get("content-length")
        if content_length:
            if int(content_length) >= settings.MAX_UPLOAD_SIZE:  # Changed > to >= for exact size limit
                raise HTTPException(
                    status_code=413,
                    detail=f"This file is too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE / 1_000_000_000:.0f}GB."
                )
            elif int(content_length) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="The file appears to be empty. Please check that it contains content."
                )
        
        # Store original receive to use after validation
        original_receive = request.receive
        chunks = []
        total_size = 0
        content_type_validated = False
        
        # Read initial chunks for validation
        while True:
            chunk = await original_receive()
            chunks.append(chunk)
            
            # Update total size
            body = chunk.get('body', b'')
            total_size += len(body)
            
            # Check total size
            if total_size >= settings.MAX_UPLOAD_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail=f"This file is too large. Maximum allowed size is {settings.MAX_UPLOAD_SIZE / 1_000_000_000:.0f}GB."
                )
            
            # Try to validate content type if we have enough data
            if not content_type_validated and total_size >= 8192:
                content_type_validated = True
                mime = magic.Magic(mime=True)
                detected_type = mime.from_buffer(b''.join(c['body'] for c in chunks))
                
                if detected_type not in settings.ALLOWED_FILE_TYPES:
                    raise HTTPException(
                        status_code=415,
                        detail=f"This file doesn't appear to be a valid audio/video file. Detected type: {detected_type}. Please ensure you're uploading a supported media file."
                    )
            
            # Check if this is the last chunk
            if chunk.get('type') == 'http.request' and not chunk.get('more_body', False):
                break
        
        # Validate first chunk for headers
        first_chunk = chunks[0]
        
        # Check for empty file
        if total_size == 0:
            raise HTTPException(
                status_code=400,
                detail="The file appears to be empty. Please check that it contains content."
            )

        # Extract filename from Content-Disposition header
        content = first_chunk['body'].decode('latin1')
        filename_match = content.find('filename="')
        if filename_match == -1:
            raise HTTPException(
                status_code=400,
                detail="Missing filename. Please provide a filename for the uploaded file."
            )

        filename_start = content.find('"', filename_match) + 1
        filename_end = content.find('"', filename_start)
        if filename_start == -1 or filename_end == -1 or filename_start >= filename_end:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename format. Please provide a valid filename."
            )

        filename = content[filename_start:filename_end]
        if not filename:
            raise HTTPException(
                status_code=400,
                detail="Missing filename. Please provide a filename for the uploaded file."
            )

        # Extract content type
        content_type_match = content.find('Content-Type: ')
        if content_type_match == -1:
            raise HTTPException(
                status_code=400,
                detail="Missing content type. Please specify the content type of the file."
            )
        content_type_start = content_type_match + len('Content-Type: ')
        content_type_end = content.find('\r\n', content_type_start)
        if content_type_end == -1:
            content_type_end = len(content)
        declared_type = content[content_type_start:content_type_end].strip()
        
        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(
                status_code=400,
                detail="This filename contains invalid characters. Please use a simple filename without special characters or paths."
            )
        
        # Check for extension spoofing
        if filename.count('.') > 1 or any(ext in filename.lower() for ext in ['.exe', '.bat', '.sh', '.cmd']):
            raise HTTPException(
                status_code=400,
                detail="This file type is not allowed for security reasons. Please upload audio or video files only."
            )
        
        # Additional content validation first
        content_sample = first_chunk['body'][:8192].decode('latin1', errors='ignore')
        if '#!/' in content_sample or 'rm -rf' in content_sample:
            raise HTTPException(
                status_code=400,
                detail="This file contains potentially harmful content and cannot be processed. Please ensure you're uploading a regular media file."
            )
        
        # MIME type validation
        mime = magic.Magic(mime=True)
        detected_type = mime.from_buffer(first_chunk['body'])
        
        # Check MIME type first
        if detected_type not in settings.ALLOWED_FILE_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"This file doesn't appear to be a valid audio/video file. Detected type: {detected_type}. Please ensure you're uploading a supported media file (MP3, WAV, OGG, MP4, or MPEG)."
            )
        
        # Then check for content type mismatch
        if detected_type != declared_type:
            raise HTTPException(
                status_code=415,
                detail=f"Content type mismatch. Declared: {declared_type}, Detected: {detected_type}"
            )
        
        # Create wrapper to return stored chunks then continue with original receive
        async def receive_wrapper():
            nonlocal chunks
            if chunks:
                chunk = chunks.pop(0)
                return chunk
            return await original_receive()
        
        # Replace receive with our wrapper
        request._receive = receive_wrapper
        
        # Continue with request
        return await call_next(request)
    
    return await call_next(request)
