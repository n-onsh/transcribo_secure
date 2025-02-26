"""Integration tests for tag functionality."""

import pytest
from uuid import uuid4
from datetime import datetime

from backend.src.models.tag import TagCreate, TagUpdate

@pytest.mark.asyncio
async def test_tag_flow(client, auth_headers):
    """Test complete tag management flow."""
    # Create a tag
    tag_data = {
        "name": "Test Tag",
        "color": "#ff0000",
        "metadata": {"key": "value"}
    }
    response = await client.post("/api/tags", json=tag_data, headers=auth_headers)
    assert response.status_code == 201
    tag_id = response.json()["tag_id"]

    # Get the created tag
    response = await client.get(f"/api/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 200
    tag = response.json()
    assert tag["name"] == tag_data["name"]
    assert tag["color"] == tag_data["color"]
    assert tag["metadata"] == tag_data["metadata"]

    # List all tags
    response = await client.get("/api/tags", headers=auth_headers)
    assert response.status_code == 200
    tags = response.json()
    assert len(tags) > 0
    assert any(t["id"] == tag_id for t in tags)

    # Update the tag
    update_data = {
        "name": "Updated Tag",
        "color": "#00ff00"
    }
    response = await client.put(f"/api/tags/{tag_id}", json=update_data, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify update
    response = await client.get(f"/api/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 200
    updated_tag = response.json()
    assert updated_tag["name"] == update_data["name"]
    assert updated_tag["color"] == update_data["color"]

    # Create a test resource (job)
    job_id = str(uuid4())

    # Assign tag to resource
    response = await client.post(
        f"/api/tags/resources/job/{job_id}/tags/{tag_id}",
        headers=auth_headers
    )
    assert response.status_code == 201
    assignment_id = response.json()["assignment_id"]

    # Get tags for resource
    response = await client.get(
        f"/api/tags/resources/job/{job_id}/tags",
        headers=auth_headers
    )
    assert response.status_code == 200
    resource_tags = response.json()
    assert len(resource_tags) == 1
    assert resource_tags[0]["id"] == tag_id

    # Get resources by tag
    response = await client.get(
        f"/api/tags/{tag_id}/resources?resource_type=job",
        headers=auth_headers
    )
    assert response.status_code == 200
    tagged_resources = response.json()
    assert job_id in tagged_resources

    # Remove tag from resource
    response = await client.delete(
        f"/api/tags/resources/job/{job_id}/tags/{tag_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify tag removal
    response = await client.get(
        f"/api/tags/resources/job/{job_id}/tags",
        headers=auth_headers
    )
    assert response.status_code == 200
    resource_tags = response.json()
    assert len(resource_tags) == 0

    # Delete the tag
    response = await client.delete(f"/api/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["success"] is True

    # Verify deletion
    response = await client.get(f"/api/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_tag_validation(client, auth_headers):
    """Test tag validation."""
    # Test invalid color format
    tag_data = {
        "name": "Invalid Color Tag",
        "color": "not-a-color"
    }
    response = await client.post("/api/tags", json=tag_data, headers=auth_headers)
    assert response.status_code == 422

    # Test missing required field
    tag_data = {
        "color": "#ff0000"
    }
    response = await client.post("/api/tags", json=tag_data, headers=auth_headers)
    assert response.status_code == 422

    # Test invalid metadata type
    tag_data = {
        "name": "Invalid Metadata Tag",
        "color": "#ff0000",
        "metadata": "not-an-object"
    }
    response = await client.post("/api/tags", json=tag_data, headers=auth_headers)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_tag_permissions(client, auth_headers, other_auth_headers):
    """Test tag permission handling."""
    # Create a tag as first user
    tag_data = {
        "name": "Permission Test Tag",
        "color": "#ff0000"
    }
    response = await client.post("/api/tags", json=tag_data, headers=auth_headers)
    assert response.status_code == 201
    tag_id = response.json()["tag_id"]

    # Try to access tag as second user
    response = await client.get(f"/api/tags/{tag_id}", headers=other_auth_headers)
    assert response.status_code == 403

    # Try to update tag as second user
    update_data = {
        "name": "Unauthorized Update"
    }
    response = await client.put(
        f"/api/tags/{tag_id}",
        json=update_data,
        headers=other_auth_headers
    )
    assert response.status_code == 403

    # Try to delete tag as second user
    response = await client.delete(f"/api/tags/{tag_id}", headers=other_auth_headers)
    assert response.status_code == 403

    # Clean up as original user
    response = await client.delete(f"/api/tags/{tag_id}", headers=auth_headers)
    assert response.status_code == 200
