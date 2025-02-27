"""Integration tests for main application."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime

from backend.src.main import app
from backend.src.utils.exceptions import (
    ValidationError,
    AuthenticationError,
    ResourceNotFoundError
)
from backend.src.types import ErrorCode

@pytest.fixture
def client() -> TestClient:
    """Get test client."""
    return TestClient(app)

def test_health_check(client: TestClient):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_not_found(client: TestClient):
    """Test 404 error handling."""
    response = client.get("/unknown")
    assert response.status_code == 404
    
    data = response.json()
    assert data["error"] == "TranscriboError"
    assert data["code"] == ErrorCode.NOT_FOUND
    assert "message" in data
    assert "request_id" in data
    assert "context" in data
    assert "request" in data

def test_validation_error(client: TestClient):
    """Test validation error handling."""
    # Missing required field
    response = client.post("/auth/login", json={})
    assert response.status_code == 400
    
    data = response.json()
    assert data["error"] == "ValidationError"
    assert data["code"] == ErrorCode.VALIDATION_ERROR
    assert "message" in data
    assert "request_id" in data
    assert "context" in data
    assert "request" in data

def test_authentication_error(client: TestClient):
    """Test authentication error handling."""
    response = client.get("/files")
    assert response.status_code == 401
    
    data = response.json()
    assert data["error"] == "AuthenticationError"
    assert data["code"] == ErrorCode.UNAUTHORIZED
    assert "message" in data
    assert "request_id" in data
    assert "context" in data
    assert "request" in data

def test_request_id_middleware(client: TestClient):
    """Test request ID middleware."""
    # Test request ID is generated
    response = client.get("/health")
    assert "x-request-id" in response.headers
    
    # Test request ID is propagated
    request_id = "test-request-id"
    response = client.get(
        "/health",
        headers={"x-request-id": request_id}
    )
    assert response.headers["x-request-id"] == request_id

def test_error_response_development(client: TestClient, monkeypatch):
    """Test error response in development environment."""
    # Set development environment
    monkeypatch.setenv("ENVIRONMENT", "development")
    
    response = client.get("/unknown")
    data = response.json()
    
    assert "traceback" in data
    assert "context" in data
    assert "request" in data

def test_error_response_production(client: TestClient, monkeypatch):
    """Test error response in production environment."""
    # Set production environment
    monkeypatch.setenv("ENVIRONMENT", "production")
    
    response = client.get("/unknown")
    data = response.json()
    
    assert "traceback" not in data
    assert "context" in data
    assert "request" in data

def test_error_response_masking(client: TestClient):
    """Test sensitive data masking in error response."""
    response = client.post(
        "/auth/login",
        json={
            "username": "test",
            "password": "secret"
        },
        headers={
            "authorization": "Bearer token123",
            "x-api-key": "secret-key"
        }
    )
    
    data = response.json()
    request_data = data["request"]
    
    # Check headers are masked
    assert request_data["headers"]["authorization"] == "********"
    assert request_data["headers"]["x-api-key"] == "********"

def test_cors_middleware(client: TestClient):
    """Test CORS middleware."""
    # Options request for CORS preflight
    response = client.options(
        "/health",
        headers={
            "origin": "http://localhost:3000",
            "access-control-request-method": "GET"
        }
    )
    
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers
    assert "access-control-allow-headers" in response.headers

def test_error_metrics(client: TestClient):
    """Test error metrics are tracked."""
    from backend.src.utils.metrics import get_metrics
    
    # Generate some errors
    client.get("/unknown")
    client.get("/files")
    client.post("/auth/login", json={})
    
    # Get metrics
    metrics = get_metrics()
    error_metrics = [
        m for m in metrics
        if m.name == "transcribo_errors_total"
    ]
    
    assert len(error_metrics) > 0
    for metric in error_metrics:
        assert "error_type" in metric.labels
        assert "status_code" in metric.labels
        assert "operation" in metric.labels
        assert metric.value > 0

def test_error_logging(client: TestClient, caplog):
    """Test error logging."""
    # Generate error
    client.get("/unknown")
    
    # Check logs
    assert len(caplog.records) > 0
    record = caplog.records[-1]
    assert record.levelname == "ERROR"
    assert "timestamp" in record.message
    assert "operation" in record.message
    assert "error_type" in record.message
    assert "details" in record.message
