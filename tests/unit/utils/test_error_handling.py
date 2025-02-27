"""Tests for error handling utilities."""

import pytest
from datetime import datetime
from fastapi import HTTPException, Request
from starlette.datastructures import Headers
from typing import Dict, Any, Optional

from backend.src.utils.error_handling import (
    ErrorResponseConfig,
    ErrorResponseFormatter,
    format_error_response
)
from backend.src.utils.exceptions import (
    TranscriboError,
    ValidationError,
    AuthenticationError,
    StorageError
)
from backend.src.types import ErrorCode

class MockRequest:
    """Mock FastAPI request for testing."""
    
    def __init__(
        self,
        method: str = "GET",
        url: str = "http://test.com",
        headers: Optional[Dict[str, str]] = None,
        client_host: str = "127.0.0.1"
    ):
        """Initialize mock request."""
        self.method = method
        self.url = url
        self.headers = Headers(headers or {})
        self.client = type("Client", (), {"host": client_host})()
        self.state = type("State", (), {"request_id": "test-request-id"})()

@pytest.fixture
def error_config() -> ErrorResponseConfig:
    """Get error response configuration for testing."""
    return ErrorResponseConfig(
        include_traceback=True,
        include_context=True,
        include_request_details=True,
        mask_sensitive_data=True,
        sensitive_fields=["password", "token", "secret"]
    )

@pytest.fixture
def error_formatter(error_config: ErrorResponseConfig) -> ErrorResponseFormatter:
    """Get error response formatter for testing."""
    return ErrorResponseFormatter(error_config)

@pytest.fixture
def mock_request() -> MockRequest:
    """Get mock request for testing."""
    return MockRequest(
        method="POST",
        url="http://test.com/api/test",
        headers={
            "user-agent": "test-agent",
            "authorization": "Bearer test-token",
            "x-request-id": "test-request-id"
        }
    )

def test_error_config_development():
    """Test development error configuration."""
    config = ErrorResponseConfig.development()
    assert config.include_traceback is True
    assert config.include_context is True
    assert config.include_request_details is True
    assert config.mask_sensitive_data is True

def test_error_config_production():
    """Test production error configuration."""
    config = ErrorResponseConfig.production()
    assert config.include_traceback is False
    assert config.include_context is True
    assert config.include_request_details is True
    assert config.mask_sensitive_data is True

def test_mask_sensitive_data(error_formatter: ErrorResponseFormatter):
    """Test sensitive data masking."""
    data = {
        "username": "test",
        "password": "secret123",
        "token": "abc123",
        "nested": {
            "secret": "hidden",
            "public": "visible"
        },
        "list": [
            {"password": "pwd123"},
            {"token": "token123"}
        ]
    }
    
    masked = error_formatter.mask_sensitive_data(data)
    
    assert masked["username"] == "test"
    assert masked["password"] == "********"
    assert masked["token"] == "********"
    assert masked["nested"]["secret"] == "********"
    assert masked["nested"]["public"] == "visible"
    assert masked["list"][0]["password"] == "********"
    assert masked["list"][1]["token"] == "********"

def test_format_request_details(
    error_formatter: ErrorResponseFormatter,
    mock_request: MockRequest
):
    """Test request details formatting."""
    details = error_formatter.format_request_details(mock_request)
    
    assert details["method"] == "POST"
    assert details["url"] == "http://test.com/api/test"
    assert details["client"] == "127.0.0.1"
    assert "headers" in details
    assert details["headers"]["authorization"] == "********"
    assert details["headers"]["user-agent"] == "test-agent"

def test_format_error_context(error_formatter: ErrorResponseFormatter):
    """Test error context formatting."""
    error_context = {
        "timestamp": datetime.utcnow(),
        "operation": "test_operation",
        "error_type": "TestError",
        "error_code": ErrorCode.INVALID_REQUEST,
        "details": {
            "password": "secret",
            "public": "visible"
        }
    }
    
    context = error_formatter.format_error_context(error_context)
    
    assert context["operation"] == "test_operation"
    assert context["error_type"] == "TestError"
    assert context["error_code"] == ErrorCode.INVALID_REQUEST
    assert context["details"]["password"] == "********"
    assert context["details"]["public"] == "visible"

def test_format_transcribo_error(
    error_formatter: ErrorResponseFormatter,
    mock_request: MockRequest
):
    """Test TranscriboError formatting."""
    error = ValidationError(
        message="Invalid input",
        details={
            "operation": "test_operation",
            "details": {
                "field": "username",
                "error": "Required"
            }
        }
    )
    
    response = error_formatter.format_error(error, mock_request)
    
    assert response.error == "ValidationError"
    assert response.code == ErrorCode.VALIDATION_ERROR
    assert response.message == "Invalid input"
    assert response.request_id == "test-request-id"
    assert response.context is not None
    assert response.request is not None
    assert response.traceback is not None

def test_format_http_exception(
    error_formatter: ErrorResponseFormatter,
    mock_request: MockRequest
):
    """Test HTTPException formatting."""
    error = HTTPException(
        status_code=404,
        detail="Resource not found"
    )
    
    response = error_formatter.format_error(error, mock_request)
    
    assert response.error == "HTTPException"
    assert response.code == ErrorCode.INTERNAL_ERROR
    assert response.message == "Resource not found"
    assert response.request_id == "test-request-id"
    assert response.context is not None
    assert response.request is not None
    assert response.traceback is not None

def test_format_unhandled_exception(
    error_formatter: ErrorResponseFormatter,
    mock_request: MockRequest
):
    """Test unhandled exception formatting."""
    error = ValueError("Something went wrong")
    
    response = error_formatter.format_error(error, mock_request)
    
    assert response.error == "ValueError"
    assert response.code == ErrorCode.INTERNAL_ERROR
    assert response.message == "Something went wrong"
    assert response.request_id == "test-request-id"
    assert response.context is not None
    assert response.request is not None
    assert response.traceback is not None

def test_format_error_response_development():
    """Test error response formatting in development."""
    error = ValidationError("Invalid input")
    request = MockRequest()
    
    response = format_error_response(
        error=error,
        request=request,
        environment="development"
    )
    
    assert response.traceback is not None
    assert response.context is not None
    assert response.request is not None

def test_format_error_response_production():
    """Test error response formatting in production."""
    error = ValidationError("Invalid input")
    request = MockRequest()
    
    response = format_error_response(
        error=error,
        request=request,
        environment="production"
    )
    
    assert response.traceback is None
    assert response.context is not None
    assert response.request is not None
