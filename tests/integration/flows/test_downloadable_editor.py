"""Integration tests for downloadable editor functionality."""

import pytest
from bs4 import BeautifulSoup

@pytest.mark.asyncio
async def test_download_editor(client, auth_headers):
    """Test downloading standalone editor."""
    # Create a test job
    job_data = {
        "name": "Test Job",
        "content": "Test content",
        "status": "completed"
    }
    response = await client.post("/api/jobs", json=job_data, headers=auth_headers)
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    # Download editor
    response = await client.get(f"/editor/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/html; charset=utf-8"
    assert response.headers["content-disposition"] == f"attachment; filename=editor_{job_id}.html"

    # Parse HTML and verify structure
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check title
    assert soup.title.string == "Transcription Editor"

    # Check required elements
    assert soup.find('video', id='media-player') is not None
    assert soup.find('div', id='segments-container') is not None
    assert soup.find('div', id='speakers-container') is not None
    assert soup.find('button', id='save-btn') is not None
    assert soup.find('button', id='export-text-btn') is not None
    assert soup.find('button', id='export-srt-btn') is not None

    # Check inline JavaScript
    scripts = soup.find_all('script')
    editor_script = None
    for script in scripts:
        if not script.get('src'):  # Look for inline script
            if 'loadEditorState' in script.string:
                editor_script = script
                break
    assert editor_script is not None

    # Check standalone mode functionality
    assert 'window.location.protocol === "file:"' in editor_script.string
    assert 'localStorage.getItem' in editor_script.string
    assert 'localStorage.setItem' in editor_script.string

@pytest.mark.asyncio
async def test_download_editor_invalid_job(client, auth_headers):
    """Test downloading editor for invalid job."""
    response = await client.get("/editor/invalid-id/download")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_download_editor_unauthorized(client):
    """Test downloading editor without authorization."""
    response = await client.get("/editor/test-job/download")
    assert response.status_code == 401
