# tests/test_backend_api.py
import pytest
from fastapi.testclient import TestClient
from backend_api.src.main import app  # Fixed absolute import

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    json_resp = response.json()
    assert json_resp.get("status") == "healthy"
    assert "timestamp" in json_resp
