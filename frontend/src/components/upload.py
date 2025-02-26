"""File upload component with enhanced UX."""

from typing import Dict, List, Optional
import json
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="src/templates")

class UploadComponent:
    """Enhanced file upload component."""
    
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
                "progress_stages": {
                    "extracting": "Extracting files from ZIP",
                    "processing": "Processing audio files",
                    "completed": "Processing complete"
                }
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
