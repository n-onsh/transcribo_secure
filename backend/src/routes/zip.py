"""ZIP file routes."""

from typing import Dict, Optional, List
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Request
from ..services.zip_handler import ZipHandler
from ..utils.logging import log_info, log_error

router = APIRouter(prefix="/zip", tags=["zip"])

@router.post("/process")
async def process_zip(
    file: UploadFile = File(...),
    metadata: Optional[Dict] = None,
    service: ZipHandler = Depends()
) -> List[Dict]:
    """Process a ZIP file."""
    try:
        file_content = await file.read()
        results = await service.process_zip(file_content, metadata)
        log_info(f"Processed ZIP file {file.filename}")
        return results
    except Exception as e:
        log_error(f"Error processing ZIP file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create")
async def create_zip(
    files: List[Dict],
    metadata: Optional[Dict] = None,
    service: ZipHandler = Depends()
) -> bytes:
    """Create a ZIP file."""
    try:
        zip_data = await service.create_zip(files, metadata)
        log_info(f"Created ZIP file with {len(files)} files")
        return zip_data
    except Exception as e:
        log_error(f"Error creating ZIP file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/validate")
async def validate_zip(
    file: UploadFile = File(...),
    service: ZipHandler = Depends()
) -> Dict:
    """Validate a ZIP file."""
    try:
        file_content = await file.read()
        validation_result = await service.validate_zip(file_content)
        log_info(f"Validated ZIP file {file.filename}")
        return validation_result
    except Exception as e:
        log_error(f"Error validating ZIP file {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/info")
async def get_zip_info(
    file: UploadFile = File(...),
    service: ZipHandler = Depends()
) -> Dict:
    """Get ZIP file information."""
    try:
        file_content = await file.read()
        info = await service.get_zip_info(file_content)
        log_info(f"Retrieved info for ZIP file {file.filename}")
        return info
    except Exception as e:
        log_error(f"Error getting ZIP file info for {file.filename}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
