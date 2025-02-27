"""Tests for error handler middleware."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from src.middleware.error_handler import ErrorHandlerMiddleware
from src.services.error_tracking import ErrorTrackingService
from src.types import (
    ErrorCode,
    ErrorSeverity,
    EnhancedErrorContext,
    RecoverySuggestion,
    ErrorResponse
)
from src.utils.exceptions import (
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    StorageError,
    TranscriptionError,
    DatabaseError,
    ZipError
)

@pytest.fixture
def app():
    """Create FastAPI app."""
    return FastAPI()

@pytest.fixture
def error_tracking_service():
    """Create mock error tracking service."""
    service = Mock(spec=ErrorTrackingService)
    service.track_error = AsyncMock()
    service.get_recovery_suggestions = AsyncMock(return_value=[
        RecoverySuggestion(
            action="Test Action",
            description="Test Description"
        )
    ])
    return service

@pytest.fixture
def error_handler(app, error_tracking_service):
    """Create error handler middleware."""
    return ErrorHandlerMiddleware(app, error_tracking_service)

@pytest.fixture
def mock_request():
    """Create mock request."""
    request = Mock(spec=Request)
    request.url.path = "/test"
    request.method = "GET"
    request.headers = {}
    request.client.host = "127.0.0.1"
    request.state.start_time = datetime.utcnow()
    request.state.request_id = "test-request"
    request.state.user_id = "test-user"
    return request

@pytest.mark.asyncio
async def test_validation_error(error_handler, mock_request):
    """Test handling validation error."""
    error = ValidationError("Invalid input")
    
    response = await error_handler._handle_validation_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert response.body is not None

@pytest.mark.asyncio
async def test_auth_errors(error_handler, mock_request):
    """Test handling authentication and authorization errors."""
    auth_error = AuthenticationError("Invalid token")
    auth_response = await error_handler._handle_auth_error(
        mock_request,
        auth_error,
        await error_handler._get_error_context(mock_request, auth_error)
    )
    assert auth_response.status_code == 401
    
    authz_error = AuthorizationError("Insufficient permissions")
    authz_response = await error_handler._handle_auth_error(
        mock_request,
        authz_error,
        await error_handler._get_error_context(mock_request, authz_error)
    )
    assert authz_response.status_code == 403

@pytest.mark.asyncio
async def test_not_found_error(error_handler, mock_request):
    """Test handling not found error."""
    error = ResourceNotFoundError("Resource not found")
    
    response = await error_handler._handle_not_found_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_storage_error(error_handler, mock_request):
    """Test handling storage error."""
    error = StorageError("Storage error")
    
    response = await error_handler._handle_storage_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 500
    content = response.body.decode()
    assert "Check Storage" in content
    assert "Check Permissions" in content

@pytest.mark.asyncio
async def test_transcription_error(error_handler, mock_request):
    """Test handling transcription error."""
    error = TranscriptionError("Transcription failed")
    
    response = await error_handler._handle_transcription_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 500
    content = response.body.decode()
    assert "Check Audio" in content
    assert "Try Different Model" in content

@pytest.mark.asyncio
async def test_database_error(error_handler, mock_request):
    """Test handling database error."""
    error = DatabaseError("Database error")
    
    response = await error_handler._handle_database_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 500
    content = response.body.decode()
    assert "Try Again" in content

@pytest.mark.asyncio
async def test_zip_error(error_handler, mock_request):
    """Test handling ZIP error."""
    error = ZipError("ZIP error")
    
    response = await error_handler._handle_zip_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 400
    content = response.body.decode()
    assert "Check ZIP File" in content
    assert "Check Contents" in content

@pytest.mark.asyncio
async def test_unknown_error(error_handler, mock_request):
    """Test handling unknown error."""
    error = Exception("Unknown error")
    
    response = await error_handler._handle_unknown_error(
        mock_request,
        error,
        await error_handler._get_error_context(mock_request, error)
    )
    
    assert response.status_code == 500
    content = response.body.decode()
    assert "Try Again" in content
    assert "Contact Support" in content

@pytest.mark.asyncio
async def test_error_tracking(error_handler, mock_request, error_tracking_service):
    """Test error tracking integration."""
    error = ValidationError("Invalid input")
    context = await error_handler._get_error_context(mock_request, error)
    
    await error_handler._handle_validation_error(mock_request, error, context)
    
    error_tracking_service.track_error.assert_called_once_with(context)

@pytest.mark.asyncio
async def test_custom_error_handler(app, error_tracking_service, mock_request):
    """Test custom error handler."""
    async def custom_handler(request, error, context):
        return JSONResponse(
            status_code=418,
            content={"message": "Custom handler"}
        )
    
    error_handler = ErrorHandlerMiddleware(
        app,
        error_tracking_service,
        error_handlers={"ValidationError": custom_handler}
    )
    
    error = ValidationError("Invalid input")
    context = await error_handler._get_error_context(mock_request, error)
    
    response = await error_handler._handle_validation_error(mock_request, error, context)
    
    assert response.status_code == 418
    assert response.body.decode() == '{"message":"Custom handler"}'

@pytest.mark.asyncio
async def test_error_response_format(error_handler, mock_request):
    """Test error response format."""
    error = ValidationError("Invalid input")
    context = await error_handler._get_error_context(mock_request, error)
    
    response = await error_handler._handle_validation_error(mock_request, error, context)
    content = response.body.decode()
    
    assert "error" in content
    assert "code" in content
    assert "message" in content
    assert "request_id" in content
    assert "details" in content
    assert "severity" in content
    assert "recovery_suggestions" in content

@pytest.mark.asyncio
async def test_error_context_details(error_handler, mock_request):
    """Test error context details."""
    error = ValidationError("Invalid input")
    context = await error_handler._get_error_context(mock_request, error)
    
    assert context.operation == "/test"
    assert context.request_id == "test-request"
    assert context.user_id == "test-user"
    assert "request" in context.details
    assert context.details["request"]["method"] == "GET"
    assert context.details["request"]["client"] == "127.0.0.1"

@pytest.mark.asyncio
async def test_dispatch_success(error_handler, mock_request):
    """Test successful request dispatch."""
    async def next_handler(request):
        return Response(status_code=200)
    
    response = await error_handler.dispatch(mock_request, next_handler)
    
    assert response.status_code == 200
    error_handler.error_tracking.track_error.assert_not_called()

@pytest.mark.asyncio
async def test_dispatch_error(error_handler, mock_request):
    """Test error in request dispatch."""
    async def next_handler(request):
        raise ValidationError("Invalid input")
    
    response = await error_handler.dispatch(mock_request, next_handler)
    
    assert response.status_code == 400
    error_handler.error_tracking.track_error.assert_called_once()
