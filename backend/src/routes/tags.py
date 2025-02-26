"""Tag routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, List, Optional

from ..models.tag import TagCreate, TagUpdate, TagResponse
from ..services.provider import service_provider
from ..services.interfaces import TagServiceInterface
from ..utils.logging import log_error
from ..utils.metrics import track_time, DB_OPERATION_DURATION

router = APIRouter(
    prefix="/tags",
    tags=["tags"]
)

@router.post(
    "/",
    response_model=Dict[str, str],
    status_code=status.HTTP_201_CREATED,
    summary="Create Tag",
    description="Create a new tag"
)
@track_time(DB_OPERATION_DURATION, {"operation": "create_tag_api"})
async def create_tag(
    tag_data: TagCreate,
    user_id: str = None  # Set by auth middleware
):
    """Create a new tag."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Create tag
        tag_id = await tag_service.create_tag(tag_data, user_id)
        
        return {"tag_id": tag_id}
    except Exception as e:
        log_error(f"Error creating tag: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/",
    response_model=List[TagResponse],
    summary="List Tags",
    description="Get all tags for the authenticated user"
)
@track_time(DB_OPERATION_DURATION, {"operation": "list_tags_api"})
async def get_tags(
    user_id: str = None  # Set by auth middleware
):
    """Get all tags for a user."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Get tags
        tags = await tag_service.get_tags(user_id)
        
        return tags
    except Exception as e:
        log_error(f"Error getting tags: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/{tag_id}",
    response_model=TagResponse,
    summary="Get Tag",
    description="Get a tag by ID"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_tag_api"})
async def get_tag(
    tag_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Get a tag by ID."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Get tag
        tag = await tag_service.get_tag(tag_id)
        
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        # Check ownership
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return tag
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting tag {tag_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put(
    "/{tag_id}",
    response_model=Dict[str, bool],
    summary="Update Tag",
    description="Update a tag"
)
@track_time(DB_OPERATION_DURATION, {"operation": "update_tag_api"})
async def update_tag(
    tag_id: str,
    updates: TagUpdate,
    user_id: str = None  # Set by auth middleware
):
    """Update a tag."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Check ownership
        tag = await tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Update tag
        success = await tag_service.update_tag(tag_id, updates)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error updating tag {tag_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete(
    "/{tag_id}",
    response_model=Dict[str, bool],
    summary="Delete Tag",
    description="Delete a tag"
)
@track_time(DB_OPERATION_DURATION, {"operation": "delete_tag_api"})
async def delete_tag(
    tag_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Delete a tag."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Check ownership
        tag = await tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Delete tag
        success = await tag_service.delete_tag(tag_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error deleting tag {tag_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.post(
    "/resources/{resource_type}/{resource_id}/tags/{tag_id}",
    response_model=Dict[str, str],
    status_code=status.HTTP_201_CREATED,
    summary="Assign Tag",
    description="Assign a tag to a resource"
)
@track_time(DB_OPERATION_DURATION, {"operation": "assign_tag_api"})
async def assign_tag(
    resource_type: str,
    resource_id: str,
    tag_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Assign a tag to a resource."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Check tag ownership
        tag = await tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Assign tag
        assignment_id = await tag_service.assign_tag(tag_id, resource_id, resource_type, user_id)
        
        return {"assignment_id": assignment_id}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error assigning tag {tag_id} to {resource_type} {resource_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.delete(
    "/resources/{resource_type}/{resource_id}/tags/{tag_id}",
    response_model=Dict[str, bool],
    summary="Remove Tag",
    description="Remove a tag from a resource"
)
@track_time(DB_OPERATION_DURATION, {"operation": "remove_tag_api"})
async def remove_tag(
    resource_type: str,
    resource_id: str,
    tag_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Remove a tag from a resource."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Check tag ownership
        tag = await tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Remove tag
        success = await tag_service.remove_tag(tag_id, resource_id, resource_type)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag assignment not found"
            )
        
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error removing tag {tag_id} from {resource_type} {resource_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/resources/{resource_type}/{resource_id}/tags",
    response_model=List[TagResponse],
    summary="Get Resource Tags",
    description="Get all tags for a resource"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_resource_tags_api"})
async def get_resource_tags(
    resource_type: str,
    resource_id: str,
    user_id: str = None  # Set by auth middleware
):
    """Get all tags for a resource."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Get tags
        tags = await tag_service.get_resource_tags(resource_id, resource_type)
        
        return tags
    except Exception as e:
        log_error(f"Error getting tags for {resource_type} {resource_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get(
    "/{tag_id}/resources",
    response_model=List[str],
    summary="Get Tagged Resources",
    description="Get all resources with a specific tag"
)
@track_time(DB_OPERATION_DURATION, {"operation": "get_resources_by_tag_api"})
async def get_resources_by_tag(
    tag_id: str,
    resource_type: Optional[str] = None,
    user_id: str = None  # Set by auth middleware
):
    """Get all resources with a specific tag."""
    try:
        # Get tag service
        tag_service = service_provider.get(TagServiceInterface)
        
        if not tag_service:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Service unavailable"
            )
        
        # Check tag ownership
        tag = await tag_service.get_tag(tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tag {tag_id} not found"
            )
        
        if tag.get("user_id") and tag.get("user_id") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get resources
        resources = await tag_service.get_resources_by_tag(tag_id, resource_type)
        
        return resources
    except HTTPException:
        raise
    except Exception as e:
        log_error(f"Error getting resources with tag {tag_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
