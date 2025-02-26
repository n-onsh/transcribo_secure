"""Tag service."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..models.tag import Tag, TagAssignment, TagCreate, TagUpdate, TagResponse
from ..utils.logging import log_error, log_info
from ..utils.metrics import track_time, DB_OPERATION_DURATION

class TagService:
    """Service for managing tags."""
    
    def __init__(self, database):
        """Initialize tag service."""
        self.database = database
        self.initialized = False
    
    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Ensure collections exist
            await self.database.create_collection("tags")
            await self.database.create_collection("tag_assignments")
            
            # Create indexes
            await self.database.tags.create_index("user_id")
            await self.database.tag_assignments.create_index([
                ("resource_id", 1),
                ("resource_type", 1)
            ])
            await self.database.tag_assignments.create_index([
                ("tag_id", 1),
                ("resource_type", 1)
            ])
            
            self.initialized = True
            log_info("Tag service initialized")
        except Exception as e:
            log_error(f"Failed to initialize tag service: {str(e)}")
            raise
    
    async def cleanup(self):
        """Clean up the service."""
        self.initialized = False
        log_info("Tag service cleaned up")
    
    @track_time(DB_OPERATION_DURATION, {"operation": "create_tag"})
    async def create_tag(self, tag_data: TagCreate, user_id: Optional[str] = None) -> str:
        """Create a new tag."""
        try:
            # Generate tag ID
            tag_id = str(uuid.uuid4())
            now = datetime.now()
            
            # Create tag record
            tag = {
                "id": tag_id,
                "name": tag_data.name,
                "color": tag_data.color,
                "created_at": now,
                "updated_at": now,
                "user_id": user_id,
                "metadata": tag_data.metadata or {}
            }
            
            # Store tag in database
            await self.database.tags.insert_one(tag)
            
            log_info(f"Created tag {tag_id} for user {user_id}")
            return tag_id
        except Exception as e:
            log_error(f"Error creating tag: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "get_tag"})
    async def get_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Get a tag by ID."""
        try:
            tag = await self.database.tags.find_one({"id": tag_id})
            return tag
        except Exception as e:
            log_error(f"Error getting tag {tag_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "get_tags"})
    async def get_tags(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all tags for a user."""
        try:
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            tags = await self.database.tags.find(query).to_list(length=None)
            return tags
        except Exception as e:
            log_error(f"Error getting tags: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "update_tag"})
    async def update_tag(self, tag_id: str, updates: TagUpdate) -> bool:
        """Update a tag."""
        try:
            # Build update document
            update_doc = {"updated_at": datetime.now()}
            
            if updates.name is not None:
                update_doc["name"] = updates.name
            
            if updates.color is not None:
                update_doc["color"] = updates.color
            
            if updates.metadata is not None:
                update_doc["metadata"] = updates.metadata
            
            # Update tag in database
            result = await self.database.tags.update_one(
                {"id": tag_id},
                {"$set": update_doc}
            )
            
            success = result.modified_count > 0
            if success:
                log_info(f"Updated tag {tag_id}")
            
            return success
        except Exception as e:
            log_error(f"Error updating tag {tag_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "delete_tag"})
    async def delete_tag(self, tag_id: str) -> bool:
        """Delete a tag."""
        try:
            # Delete tag from database
            result = await self.database.tags.delete_one({"id": tag_id})
            
            # Delete tag assignments
            await self.database.tag_assignments.delete_many({"tag_id": tag_id})
            
            success = result.deleted_count > 0
            if success:
                log_info(f"Deleted tag {tag_id}")
            
            return success
        except Exception as e:
            log_error(f"Error deleting tag {tag_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "assign_tag"})
    async def assign_tag(
        self, tag_id: str, resource_id: str, resource_type: str, user_id: Optional[str] = None
    ) -> str:
        """Assign a tag to a resource."""
        try:
            # Check if tag exists
            tag = await self.get_tag(tag_id)
            if not tag:
                raise ValueError(f"Tag {tag_id} not found")
            
            # Check if assignment already exists
            existing = await self.database.tag_assignments.find_one({
                "tag_id": tag_id,
                "resource_id": resource_id,
                "resource_type": resource_type
            })
            
            if existing:
                return existing["id"]
            
            # Generate assignment ID
            assignment_id = str(uuid.uuid4())
            
            # Create assignment record
            assignment = {
                "id": assignment_id,
                "tag_id": tag_id,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "created_at": datetime.now(),
                "user_id": user_id,
                "metadata": {}
            }
            
            # Store assignment in database
            await self.database.tag_assignments.insert_one(assignment)
            
            log_info(f"Assigned tag {tag_id} to {resource_type} {resource_id}")
            return assignment_id
        except Exception as e:
            log_error(f"Error assigning tag {tag_id} to {resource_type} {resource_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "remove_tag"})
    async def remove_tag(self, tag_id: str, resource_id: str, resource_type: str) -> bool:
        """Remove a tag from a resource."""
        try:
            # Delete assignment from database
            result = await self.database.tag_assignments.delete_one({
                "tag_id": tag_id,
                "resource_id": resource_id,
                "resource_type": resource_type
            })
            
            success = result.deleted_count > 0
            if success:
                log_info(f"Removed tag {tag_id} from {resource_type} {resource_id}")
            
            return success
        except Exception as e:
            log_error(f"Error removing tag {tag_id} from {resource_type} {resource_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "get_resource_tags"})
    async def get_resource_tags(self, resource_id: str, resource_type: str) -> List[Dict[str, Any]]:
        """Get all tags for a resource."""
        try:
            # Get tag assignments for resource
            assignments = await self.database.tag_assignments.find({
                "resource_id": resource_id,
                "resource_type": resource_type
            }).to_list(length=None)
            
            # Get tag IDs
            tag_ids = [assignment["tag_id"] for assignment in assignments]
            
            if not tag_ids:
                return []
            
            # Get tags
            tags = await self.database.tags.find({"id": {"$in": tag_ids}}).to_list(length=None)
            
            return tags
        except Exception as e:
            log_error(f"Error getting tags for {resource_type} {resource_id}: {str(e)}")
            raise
    
    @track_time(DB_OPERATION_DURATION, {"operation": "get_resources_by_tag"})
    async def get_resources_by_tag(self, tag_id: str, resource_type: Optional[str] = None) -> List[str]:
        """Get all resources with a specific tag."""
        try:
            # Build query
            query = {"tag_id": tag_id}
            if resource_type:
                query["resource_type"] = resource_type
            
            # Get tag assignments
            assignments = await self.database.tag_assignments.find(query).to_list(length=None)
            
            # Get resource IDs
            resource_ids = [assignment["resource_id"] for assignment in assignments]
            
            return resource_ids
        except Exception as e:
            log_error(f"Error getting resources with tag {tag_id}: {str(e)}")
            raise
