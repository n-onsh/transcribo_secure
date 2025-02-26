"""Hash verification routes."""

from fastapi import APIRouter, HTTPException, status
from typing import Optional

from ..services.provider import service_provider
from ..services.interfaces import StorageInterface
from ..utils.logging import log_error
from ..utils.hash_verification import verify_file_hash, HashVerificationError

router = APIRouter(
    prefix="/verify",
    tags=["verification"]
)

@router.get(
    "/files/{file_id}",
    summary="Verify File Hash",
    description="Verify a file's hash matches the expected value"
)
async def verify_file_hash_endpoint(
    file_id: str,
    expected_hash: str,
    algorithm: Optional[str] = "sha256",
    user_id: str = None  # Set by auth middleware
):
    """Verify a file's hash matches the expected value."""
    try:
        # Get storage service
        storage = service_provider.get(StorageInterface)
        if not storage:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get file path
        file_info = await storage.get_file_info(file_id)
        if not file_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {file_id} not found"
            )

        # Verify hash
        try:
            is_valid = verify_file_hash(file_info["path"], expected_hash, algorithm)
        except HashVerificationError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

        return {
            "file_id": file_id,
            "is_valid": is_valid,
            "expected_hash": expected_hash,
            "algorithm": algorithm
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error verifying hash for file {file_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to verify file hash"
        )
