"""File upload component with enhanced UX and ZIP handling."""

import os
import uuid
import json
import asyncio
import zipfile
import tempfile
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any
from fastapi import Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from ..utils.metrics import (
    UPLOAD_REQUESTS,
    UPLOAD_ERRORS,
    track_upload_request,
    track_upload_error
)
from ..utils.logging import log_info, log_error, log_warning

templates = Jinja2Templates(directory="src/templates")

class UploadComponent:
    """Enhanced file upload component with ZIP support."""
    
    def __init__(self):
        """Initialize upload component."""
        self.supported_languages = [
            {"code": "de", "name": "German", "description": "Standard German (Hochdeutsch)"},
            {"code": "en", "name": "English", "description": "US/UK English"},
            {"code": "fr", "name": "French", "description": "Standard French"},
            {"code": "it", "name": "Italian", "description": "Standard Italian"}
        ]
        
        self.file_types = [
            {"extension": ".mp3", "description": "MP3 Audio (recommended)"},
            {"extension": ".wav", "description": "WAV Audio (large files)"},
            {"extension": ".m4a", "description": "M4A Audio (Apple)"},
            {"extension": ".zip", "description": "ZIP Archive (multiple files)"}
        ]
        
        self.validation_rules = {
            "single_file": {
                "max_size": 1024 * 1024 * 1024,  # 1GB
                "types": [".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov"]
            },
            "zip_file": {
                "max_size": 1024 * 1024 * 1024 * 12,  # 12GB
                "max_files": 100,
                "types": [".zip"],
                "allowed_content": [".mp3", ".wav", ".m4a", ".aac", ".mp4", ".mov"]
            }
        }
        
        self.progress_stages = {
            "uploading": {
                "label": "Uploading file",
                "description": "Transferring file to server"
            },
            "validating": {
                "label": "Validating file",
                "description": "Checking file integrity and format"
            },
            "extracting": {
                "label": "Extracting files",
                "description": "Extracting audio files from ZIP archive"
            },
            "processing": {
                "label": "Processing files",
                "description": "Processing audio files for transcription"
            },
            "completed": {
                "label": "Processing complete",
                "description": "All files have been processed"
            },
            "failed": {
                "label": "Processing failed",
                "description": "An error occurred during processing"
            }
        }
        
        # Active uploads tracking
        self.active_uploads: Dict[str, Dict[str, Any]] = {}

    async def render(
        self,
        request: Request,
        selected_language: Optional[str] = None,
        errors: Optional[Dict[str, str]] = None,
        job_status: Optional[Dict] = None
    ) -> HTMLResponse:
        """Render upload component."""
        return templates.TemplateResponse(
            "upload.html",
            {
                "request": request,
                "languages": self.supported_languages,
                "file_types": self.file_types,
                "validation": json.dumps(self.validation_rules),
                "selected_language": selected_language,
                "errors": errors,
                "job_status": job_status,
                "progress_stages": self.progress_stages,
                "active_uploads": self.active_uploads
            }
        )

    def get_language_info(self, language_code: str) -> Optional[Dict]:
        """Get language information."""
        for lang in self.supported_languages:
            if lang["code"] == language_code:
                return lang
        return None

    def validate_file(
        self,
        file_name: str,
        file_size: int,
        is_zip: bool = False,
        zip_contents: Optional[List[str]] = None
    ) -> List[str]:
        """Validate file against rules."""
        errors = []
        rules = self.validation_rules["zip_file" if is_zip else "single_file"]
        
        # Check file size
        if file_size > rules["max_size"]:
            errors.append(
                f"File too large. Maximum size is "
                f"{rules['max_size'] / (1024 * 1024 * 1024):.1f}GB"
            )
        
        # Check file type
        file_ext = file_name.lower()[file_name.rfind("."):]
        if file_ext not in rules["types"]:
            errors.append(
                f"Invalid file type. Supported types: "
                f"{', '.join(rules['types'])}"
            )
        
        # Validate ZIP contents if provided
        if is_zip and zip_contents:
            # Check number of files
            if len(zip_contents) > rules["max_files"]:
                errors.append(
                    f"Too many files in ZIP. Maximum is {rules['max_files']} files"
                )
            
            # Check file types in ZIP
            invalid_files = []
            for zip_file in zip_contents:
                zip_ext = zip_file.lower()[zip_file.rfind("."):]
                if zip_ext not in rules["allowed_content"]:
                    invalid_files.append(zip_file)
            
            if invalid_files:
                errors.append(
                    f"Invalid files in ZIP: {', '.join(invalid_files)}. "
                    f"Supported types: {', '.join(rules['allowed_content'])}"
                )
        
        return errors

    def get_help_text(self, topic: str) -> str:
        """Get help text for tooltips."""
        help_texts = {
            "language": """
                Select the primary language of your audio files.
                This helps optimize transcription accuracy.
                You can change this per file in batch uploads.
            """,
            
            "file_types": """
                MP3: Best balance of quality and size
                WAV: Highest quality, very large files
                M4A: Good quality, Apple format
                ZIP: Upload multiple files at once
            """,
            
            "batch_upload": """
                ZIP files can contain multiple audio files.
                Supported formats: MP3, WAV, M4A, AAC, MP4, MOV
                Maximum 100 files per ZIP, up to 12GB total.
                Files are processed in parallel for efficiency.
                Progress tracking for extraction and processing.
            """,
            
            "processing_time": """
                Processing time depends on:
                - File duration
                - Audio quality
                - Selected language
                - Current system load
                You'll see estimated times after upload.
            """
        }
        return help_texts.get(topic, "")

    async def handle_upload(
        self,
        file: UploadFile,
        language: str,
        request: Request
    ) -> JSONResponse:
        """Handle file upload with progress tracking.
        
        Args:
            file: Uploaded file
            language: Selected language code
            request: FastAPI request object
            
        Returns:
            JSON response with upload result
        """
        UPLOAD_REQUESTS.inc()
        track_upload_request()
        
        try:
            # Generate upload ID
            upload_id = str(uuid.uuid4())
            
            # Initialize upload tracking
            self.active_uploads[upload_id] = {
                "file_name": file.filename,
                "language": language,
                "stage": "uploading",
                "progress": 0,
                "start_time": datetime.utcnow(),
                "errors": []
            }
            
            # Validate file
            is_zip = file.filename.lower().endswith('.zip')
            errors = self.validate_file(
                file_name=file.filename,
                file_size=file.size,
                is_zip=is_zip
            )
            
            if errors:
                UPLOAD_ERRORS.inc()
                track_upload_error()
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "errors": errors
                    }
                )
            
            # Update stage
            self.active_uploads[upload_id]["stage"] = "validating"
            
            # Save file to temporary location
            temp_dir = tempfile.mkdtemp()
            temp_path = os.path.join(temp_dir, file.filename)
            
            try:
                # Save with progress tracking
                with open(temp_path, 'wb') as f:
                    total_size = 0
                    chunk_size = 8192
                    
                    while chunk := await file.read(chunk_size):
                        f.write(chunk)
                        total_size += len(chunk)
                        
                        # Update progress
                        if file.size:
                            progress = (total_size / file.size) * 100
                            self.active_uploads[upload_id]["progress"] = progress
                
                # Process file based on type
                if is_zip:
                    return await self._handle_zip_upload(
                        upload_id,
                        temp_path,
                        language,
                        request
                    )
                else:
                    return await self._handle_single_upload(
                        upload_id,
                        temp_path,
                        language,
                        request
                    )
                    
            finally:
                # Clean up temporary files
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    if os.path.exists(temp_dir):
                        os.rmdir(temp_dir)
                except Exception as e:
                    log_warning(f"Failed to clean up temporary files: {str(e)}")
                
                # Remove upload tracking
                if upload_id in self.active_uploads:
                    del self.active_uploads[upload_id]
                    
        except Exception as e:
            UPLOAD_ERRORS.inc()
            track_upload_error()
            log_error(f"Upload error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Internal server error"
                }
            )

    async def _handle_zip_upload(
        self,
        upload_id: str,
        file_path: str,
        language: str,
        request: Request
    ) -> JSONResponse:
        """Handle ZIP file upload.
        
        Args:
            upload_id: Upload tracking ID
            file_path: Path to temporary file
            language: Selected language code
            request: FastAPI request object
            
        Returns:
            JSON response with upload result
        """
        try:
            # Update stage
            self.active_uploads[upload_id]["stage"] = "processing"
            
            # Validate ZIP contents
            with zipfile.ZipFile(file_path) as zip_ref:
                contents = [info.filename for info in zip_ref.filelist]
                errors = self.validate_file(
                    file_name=file_path,
                    file_size=os.path.getsize(file_path),
                    is_zip=True,
                    zip_contents=contents
                )
                
                if errors:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "errors": errors
                        }
                    )
            
            # Process ZIP file
            result = await self._process_zip_file(
                upload_id,
                file_path,
                language,
                request
            )
            
            return JSONResponse(
                content={
                    "success": True,
                    "job_id": result["job_id"],
                    "is_zip": True
                }
            )
            
        except Exception as e:
            log_error(f"ZIP processing error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Failed to process ZIP file"
                }
            )

    async def _handle_single_upload(
        self,
        upload_id: str,
        file_path: str,
        language: str,
        request: Request
    ) -> JSONResponse:
        """Handle single file upload.
        
        Args:
            upload_id: Upload tracking ID
            file_path: Path to temporary file
            language: Selected language code
            request: FastAPI request object
            
        Returns:
            JSON response with upload result
        """
        try:
            # Update stage
            self.active_uploads[upload_id]["stage"] = "processing"
            
            # Create form data
            form = aiohttp.FormData()
            form.add_field(
                'file',
                open(file_path, 'rb'),
                filename=os.path.basename(file_path)
            )
            form.add_field('language', language)
            
            # Send to API
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{request.base_url}api/files/upload",
                    data=form
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        return JSONResponse(
                            status_code=response.status,
                            content=result
                        )
                    
                    return JSONResponse(
                        content={
                            "success": True,
                            "job_id": result["job_id"],
                            "is_zip": False
                        }
                    )
                    
        except Exception as e:
            log_error(f"File upload error: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": "Failed to upload file"
                }
            )

    async def _process_zip_file(
        self,
        upload_id: str,
        file_path: str,
        language: str,
        request: Request
    ) -> Dict:
        """Process ZIP file and track progress.
        
        Args:
            upload_id: Upload tracking ID
            file_path: Path to temporary file
            language: Selected language code
            request: FastAPI request object
            
        Returns:
            Processing result
        """
        # Create form data
        form = aiohttp.FormData()
        form.add_field(
            'file',
            open(file_path, 'rb'),
            filename=os.path.basename(file_path)
        )
        form.add_field('language', language)
        
        # Send to API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{request.base_url}api/zip/process",
                data=form
            ) as response:
                result = await response.json()
                
                if response.status != 200:
                    raise Exception(result.get("error", "ZIP processing failed"))
                
                job_id = result["job_id"]
                
                # Poll progress
                while True:
                    async with session.get(
                        f"{request.base_url}api/jobs/{job_id}/status"
                    ) as status_response:
                        status = await status_response.json()
                        
                        if status["status"] == "completed":
                            self.active_uploads[upload_id]["stage"] = "completed"
                            self.active_uploads[upload_id]["progress"] = 100
                            break
                            
                        elif status["status"] == "failed":
                            raise Exception(status.get("error", "Processing failed"))
                            
                        elif status.get("zip_progress"):
                            progress = status["zip_progress"]
                            self.active_uploads[upload_id].update({
                                "stage": progress["stage"],
                                "progress": progress["percent"]
                            })
                        
                        await asyncio.sleep(1)
                
                return result

    async def get_upload_status(self, upload_id: str) -> Dict:
        """Get current upload status.
        
        Args:
            upload_id: Upload tracking ID
            
        Returns:
            Upload status information
        """
        if upload_id not in self.active_uploads:
            return {
                "success": False,
                "error": "Upload not found"
            }
            
        status = self.active_uploads[upload_id].copy()
        
        # Add elapsed time
        start_time = status["start_time"]
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        status["elapsed_seconds"] = elapsed
        
        # Add stage information
        stage_info = self.progress_stages.get(status["stage"], {})
        status["stage_label"] = stage_info.get("label", status["stage"])
        status["stage_description"] = stage_info.get("description", "")
        
        return {
            "success": True,
            "status": status
        }
