# tests/test_backend_api.py
import pytest
from fastapi.testclient import TestClient

# Import your FastAPI app.
# Adjust the import according to your project structure.
from main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    # Expect a 200 OK status code.
    assert response.status_code == 200
    json_resp = response.json()
    # Confirm that the response indicates a healthy status.
    assert json_resp.get("status") == "healthy"
    assert "timestamp" in json_resp
