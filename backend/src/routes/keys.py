from fastapi import APIRouter, HTTPException, Request, Depends
from typing import Dict, List
import logging
from ..middleware.auth import AuthMiddleware
from ..services.key_management import KeyManagementService
from ..services.file_key_service import FileKeyService
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/keys",
    tags=["keys"]
)

# Initialize services
auth = AuthMiddleware()
key_service = KeyManagementService()
file_key_service = FileKeyService()

class ShareKeyRequest(BaseModel):
    """Request model for sharing file key"""
    file_id: str
    recipient_id: str

class FileKeyResponse(BaseModel):
    """Response model for file key info"""
    file_id: str
    owner_id: str
    shared_with: List[str]

@router.post("/share", response_model=FileKeyResponse)
async def share_file_key(request: Request, share_request: ShareKeyRequest):
    """Share file key with another user"""
    try:
        # Get current user
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Get file key record
        file_key_record = await file_key_service.get_file_key(share_request.file_id)
        if not file_key_record:
            raise HTTPException(
                status_code=404,
                detail="File key not found"
            )

        # Verify ownership
        if file_key_record.owner_id != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to share this file"
            )

        # Get keys for both users
        owner_key = key_service.derive_user_key(user["id"])
        recipient_key = key_service.derive_user_key(share_request.recipient_id)

        # Re-encrypt file key for recipient
        encrypted_key = key_service.share_file_key(
            file_key_record.encrypted_key,
            owner_key,
            recipient_key
        )

        # Store shared key
        await file_key_service.add_shared_key(
            file_id=share_request.file_id,
            user_id=share_request.recipient_id,
            encrypted_key=encrypted_key
        )

        # Get updated record
        updated_record = await file_key_service.get_file_key(share_request.file_id)
        return FileKeyResponse(
            file_id=updated_record.file_id,
            owner_id=updated_record.owner_id,
            shared_with=updated_record.shared_with
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to share file key: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to share file key"
        )

@router.get("/shared", response_model=List[FileKeyResponse])
async def get_shared_files(request: Request):
    """Get list of files shared with user"""
    try:
        # Get current user
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Get shared files
        shared_files = await file_key_service.get_shared_files(user["id"])
        return [
            FileKeyResponse(
                file_id=record.file_id,
                owner_id=record.owner_id,
                shared_with=record.shared_with
            )
            for record in shared_files
        ]

    except Exception as e:
        logger.error(f"Failed to get shared files: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get shared files"
        )

@router.delete("/share/{file_id}/{user_id}")
async def revoke_file_access(file_id: str, user_id: str, request: Request):
    """Revoke user's access to file"""
    try:
        # Get current user
        user = auth.get_user(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        # Get file key record
        file_key_record = await file_key_service.get_file_key(file_id)
        if not file_key_record:
            raise HTTPException(
                status_code=404,
                detail="File key not found"
            )

        # Verify ownership
        if file_key_record.owner_id != user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Not authorized to modify file access"
            )

        # Remove shared key
        await file_key_service.remove_shared_key(file_id, user_id)
        return {"status": "success"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke file access: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to revoke file access"
        )
