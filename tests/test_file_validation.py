# tests/test_file_validation.py
import io
import pytest
from fastapi.testclient import TestClient
from main import app  # Adjust the import as necessary

client = TestClient(app)

def test_file_too_large(monkeypatch):
    # Set a very low MAX_UPLOAD_SIZE to force rejection.
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "10")  # 10 bytes
    file_content = io.BytesIO(b"This file is definitely too large")
    files = {"file": ("test.mp4", file_content, "video/mp4")}

    response = client.post("/api/v1/files/", files=files)
    # Expect HTTP 413 (Payload Too Large).
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
