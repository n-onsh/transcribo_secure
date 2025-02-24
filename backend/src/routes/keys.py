from fastapi import APIRouter, HTTPException, status
from typing import List
from ..models.file_key import FileKeyResponse, FileKeyShareResponse
from ..services.interfaces import StorageInterface, DatabaseInterface
from ..services.provider import service_provider
from ..utils.exceptions import ResourceNotFoundError, AuthorizationError
from ..utils.metrics import track_time, DB_OPERATION_DURATION

router = APIRouter(
    prefix="/keys",
    tags=["keys"]
)

@router.get(
    "/files/{file_id}/key",
    response_model=FileKeyResponse,
    summary="Get File Key",
    description="Get encryption key for a file"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_file_key"})
async def get_file_key(
    file_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Get file encryption key"""
    try:
        # Get required services
        db = service_provider.get(DatabaseInterface)
        if not db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get file key
        file_key = await db.get_file_key(file_id)
        if not file_key:
            raise ResourceNotFoundError("file_key", file_id)

        # Verify ownership
        if file_key.owner_id != user_id:
            # Check if user has shared access
            share = await db.get_file_key_share(file_id, user_id)
            if not share:
                raise AuthorizationError("Access denied")

        return FileKeyResponse(
            file_id=file_key.file_id,
            owner_id=file_key.owner_id,
            encrypted_key=file_key.encrypted_key,
            created_at=file_key.created_at,
            updated_at=file_key.updated_at
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File key {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/files/{file_id}/shares",
    response_model=List[FileKeyShareResponse],
    summary="List Key Shares",
    description="List users with access to a file key"
)
@track_time(DB_OPERATION_DURATION, {"operation": "list_file_key_shares"})
async def list_file_key_shares(
    file_id: str,
    user_id: str = None  # Set by auth middleware
):
    """List file key shares"""
    try:
        # Get required services
        db = service_provider.get(DatabaseInterface)
        if not db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get file key to verify ownership
        file_key = await db.get_file_key(file_id)
        if not file_key:
            raise ResourceNotFoundError("file_key", file_id)

        # Only owner can list shares
        if file_key.owner_id != user_id:
            raise AuthorizationError("Access denied")

        # Get shares
        shares = await db.list_file_key_shares(file_id)

        return [
            FileKeyShareResponse(
                file_id=share.file_id,
                user_id=share.user_id,
                encrypted_key=share.encrypted_key,
                created_at=share.created_at,
                updated_at=share.updated_at
            )
            for share in shares
        ]

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File key {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post(
    "/files/{file_id}/shares/{user_id}",
    response_model=FileKeyShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Share Key",
    description="Share a file key with another user"
)
@track_time(DB_OPERATION_DURATION, {"operation": "create_file_key_share"})
async def create_file_key_share(
    file_id: str,
    shared_user_id: str,
    current_user_id: str = None  # Set by auth middleware
):
    """Share file key with another user"""
    try:
        # Get required services
        db = service_provider.get(DatabaseInterface)
        if not db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get file key to verify ownership
        file_key = await db.get_file_key(file_id)
        if not file_key:
            raise ResourceNotFoundError("file_key", file_id)

        # Only owner can share
        if file_key.owner_id != current_user_id:
            raise AuthorizationError("Access denied")

        # Create share
        share = await db.create_file_key_share({
            "file_id": file_id,
            "user_id": shared_user_id,
            "encrypted_key": file_key.encrypted_key
        })

        return FileKeyShareResponse(
            file_id=share.file_id,
            user_id=share.user_id,
            encrypted_key=share.encrypted_key,
            created_at=share.created_at,
            updated_at=share.updated_at
        )

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File key {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete(
    "/files/{file_id}/shares/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove Share",
    description="Remove a user's access to a file key"
)
@track_time(DB_OPERATION_DURATION, {"operation": "delete_file_key_share"})
async def delete_file_key_share(
    file_id: str,
    shared_user_id: str,
    current_user_id: str = None  # Set by auth middleware
):
    """Remove file key share"""
    try:
        # Get required services
        db = service_provider.get(DatabaseInterface)
        if not db:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )

        # Get file key to verify ownership
        file_key = await db.get_file_key(file_id)
        if not file_key:
            raise ResourceNotFoundError("file_key", file_id)

        # Only owner can remove shares
        if file_key.owner_id != current_user_id:
            raise AuthorizationError("Access denied")

        # Delete share
        await db.delete_file_key_share(file_id, shared_user_id)

    except ResourceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File key {file_id} not found"
        )
    except AuthorizationError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
