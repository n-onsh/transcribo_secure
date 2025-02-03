import io
import pytest
from fastapi.testclient import TestClient
from backend_api.src.main import app

client = TestClient(app)

def test_file_too_large(monkeypatch):
    # Set MAX_UPLOAD_SIZE to a very low value to force size rejection.
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "10")  # 10 bytes
    
    # Create a dummy MP4 file with a minimal valid header.
    # This dummy header is just an example; you may adjust it if necessary.
    dummy_mp4_header = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom'
    # Append extra data to exceed 10 bytes.
    file_content = io.BytesIO(dummy_mp4_header + b"extra data")
    
    files = {"file": ("test.mp4", file_content, "video/mp4")}
    response = client.post("/api/v1/files/", files=files)
    # Now that the MIME type is valid, the size check should trigger a 413.
    assert response.status_code == 413

def test_invalid_mime_type(monkeypatch):
    # Set MAX_UPLOAD_SIZE high enough so size is not an issue.
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "1000000")
    file_content = io.BytesIO(b"fake content")
    # Using a MIME type of text/plain which is not allowed.
    files = {"file": ("test.txt", file_content, "text/plain")}
    response = client.post("/api/v1/files/", files=files)
    # Expect HTTP 415 (Unsupported Media Type).
    assert response.status_code == 415
