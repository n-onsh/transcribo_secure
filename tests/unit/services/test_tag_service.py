"""Tests for tag service."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from backend.src.services.tag_service import TagService
from backend.src.models.tag import TagCreate, TagUpdate

@pytest.fixture
def mock_database():
    """Create mock database."""
    db = MagicMock()
    db.tags = AsyncMock()
    db.tag_assignments = AsyncMock()
    db.create_collection = AsyncMock()
    db.tags.create_index = AsyncMock()
    db.tag_assignments.create_index = AsyncMock()
    return db

@pytest.fixture
async def tag_service(mock_database):
    """Create tag service with mock database."""
    service = TagService(mock_database)
    await service.initialize()
    return service

@pytest.mark.asyncio
async def test_create_tag(tag_service, mock_database):
    """Test creating a tag."""
    # Setup
    tag_data = TagCreate(
        name="Test Tag",
        color="#ff0000",
        metadata={"key": "value"}
    )
    user_id = "test-user"

    # Execute
    tag_id = await tag_service.create_tag(tag_data, user_id)

    # Verify
    mock_database.tags.insert_one.assert_called_once()
    call_args = mock_database.tags.insert_one.call_args[0][0]
    assert call_args["id"] == tag_id
    assert call_args["name"] == tag_data.name
    assert call_args["color"] == tag_data.color
    assert call_args["user_id"] == user_id
    assert call_args["metadata"] == tag_data.metadata
    assert isinstance(call_args["created_at"], datetime)
    assert isinstance(call_args["updated_at"], datetime)

@pytest.mark.asyncio
async def test_get_tag(tag_service, mock_database):
    """Test getting a tag."""
    # Setup
    tag_id = "test-tag"
    mock_tag = {
        "id": tag_id,
        "name": "Test Tag",
        "color": "#ff0000"
    }
    mock_database.tags.find_one.return_value = mock_tag

    # Execute
    result = await tag_service.get_tag(tag_id)

    # Verify
    mock_database.tags.find_one.assert_called_once_with({"id": tag_id})
    assert result == mock_tag

@pytest.mark.asyncio
async def test_get_tags(tag_service, mock_database):
    """Test getting all tags."""
    # Setup
    user_id = "test-user"
    mock_tags = [
        {"id": "1", "name": "Tag 1"},
        {"id": "2", "name": "Tag 2"}
    ]
    mock_database.tags.find.return_value.to_list.return_value = mock_tags

    # Execute
    result = await tag_service.get_tags(user_id)

    # Verify
    mock_database.tags.find.assert_called_once_with({"user_id": user_id})
    assert result == mock_tags

@pytest.mark.asyncio
async def test_update_tag(tag_service, mock_database):
    """Test updating a tag."""
    # Setup
    tag_id = "test-tag"
    updates = TagUpdate(
        name="Updated Tag",
        color="#00ff00"
    )
    mock_database.tags.update_one.return_value.modified_count = 1

    # Execute
    result = await tag_service.update_tag(tag_id, updates)

    # Verify
    mock_database.tags.update_one.assert_called_once()
    call_args = mock_database.tags.update_one.call_args
    assert call_args[0][0] == {"id": tag_id}
    assert "name" in call_args[0][1]["$set"]
    assert "color" in call_args[0][1]["$set"]
    assert "updated_at" in call_args[0][1]["$set"]
    assert result is True

@pytest.mark.asyncio
async def test_delete_tag(tag_service, mock_database):
    """Test deleting a tag."""
    # Setup
    tag_id = "test-tag"
    mock_database.tags.delete_one.return_value.deleted_count = 1

    # Execute
    result = await tag_service.delete_tag(tag_id)

    # Verify
    mock_database.tags.delete_one.assert_called_once_with({"id": tag_id})
    mock_database.tag_assignments.delete_many.assert_called_once_with({"tag_id": tag_id})
    assert result is True

@pytest.mark.asyncio
async def test_assign_tag(tag_service, mock_database):
    """Test assigning a tag to a resource."""
    # Setup
    tag_id = "test-tag"
    resource_id = "test-resource"
    resource_type = "job"
    user_id = "test-user"

    # Mock tag exists
    mock_database.tags.find_one.return_value = {"id": tag_id}

    # Mock assignment doesn't exist
    mock_database.tag_assignments.find_one.return_value = None

    # Execute
    assignment_id = await tag_service.assign_tag(tag_id, resource_id, resource_type, user_id)

    # Verify
    mock_database.tag_assignments.insert_one.assert_called_once()
    call_args = mock_database.tag_assignments.insert_one.call_args[0][0]
    assert call_args["id"] == assignment_id
    assert call_args["tag_id"] == tag_id
    assert call_args["resource_id"] == resource_id
    assert call_args["resource_type"] == resource_type
    assert call_args["user_id"] == user_id

@pytest.mark.asyncio
async def test_remove_tag(tag_service, mock_database):
    """Test removing a tag from a resource."""
    # Setup
    tag_id = "test-tag"
    resource_id = "test-resource"
    resource_type = "job"
    mock_database.tag_assignments.delete_one.return_value.deleted_count = 1

    # Execute
    result = await tag_service.remove_tag(tag_id, resource_id, resource_type)

    # Verify
    mock_database.tag_assignments.delete_one.assert_called_once_with({
        "tag_id": tag_id,
        "resource_id": resource_id,
        "resource_type": resource_type
    })
    assert result is True

@pytest.mark.asyncio
async def test_get_resource_tags(tag_service, mock_database):
    """Test getting tags for a resource."""
    # Setup
    resource_id = "test-resource"
    resource_type = "job"
    mock_assignments = [
        {"tag_id": "1"},
        {"tag_id": "2"}
    ]
    mock_tags = [
        {"id": "1", "name": "Tag 1"},
        {"id": "2", "name": "Tag 2"}
    ]
    mock_database.tag_assignments.find.return_value.to_list.return_value = mock_assignments
    mock_database.tags.find.return_value.to_list.return_value = mock_tags

    # Execute
    result = await tag_service.get_resource_tags(resource_id, resource_type)

    # Verify
    mock_database.tag_assignments.find.assert_called_once_with({
        "resource_id": resource_id,
        "resource_type": resource_type
    })
    mock_database.tags.find.assert_called_once_with({"id": {"$in": ["1", "2"]}})
    assert result == mock_tags

@pytest.mark.asyncio
async def test_get_resources_by_tag(tag_service, mock_database):
    """Test getting resources with a specific tag."""
    # Setup
    tag_id = "test-tag"
    resource_type = "job"
    mock_assignments = [
        {"resource_id": "1"},
        {"resource_id": "2"}
    ]
    mock_database.tag_assignments.find.return_value.to_list.return_value = mock_assignments

    # Execute
    result = await tag_service.get_resources_by_tag(tag_id, resource_type)

    # Verify
    mock_database.tag_assignments.find.assert_called_once_with({
        "tag_id": tag_id,
        "resource_type": resource_type
    })
    assert result == ["1", "2"]
