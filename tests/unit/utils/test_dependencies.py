"""Tests for FastAPI dependency functions."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from fastapi import Request, HTTPException

from backend.src.utils.dependencies import (
    get_provider,
    get_service,
    DatabaseServiceDep,
    StorageServiceDep
)
from backend.src.services.provider import ServiceProvider, service_provider
from backend.src.services.base import BaseService
from backend.src.utils.exceptions import DependencyError

# Test services
class TestService(BaseService):
    """Test service."""
    pass

class TestRequest:
    """Mock FastAPI request."""
    
    def __init__(self, request_id: str = "test-request-id"):
        """Initialize request."""
        self.state = Mock()
        self.state.request_id = request_id

@pytest.fixture
def request() -> Request:
    """Get mock request."""
    return TestRequest()

@pytest.fixture
def provider() -> ServiceProvider:
    """Get service provider for testing."""
    provider = ServiceProvider()
    provider._initialized = False  # Reset for testing
    provider.__init__()
    return provider

def test_get_provider(request):
    """Test get_provider dependency."""
    result = get_provider(request)
    assert result is service_provider

def test_get_service_success(request, provider):
    """Test get_service dependency success."""
    # Register test service
    service = TestService()
    provider.register(TestService, service)
    
    # Create dependency
    dependency = get_service(TestService)
    
    # Get service
    result = dependency(request=request, provider=provider)
    assert result is service

def test_get_service_not_found(request, provider):
    """Test get_service dependency service not found."""
    # Create dependency
    dependency = get_service(TestService)
    
    # Try to get unregistered service
    with pytest.raises(DependencyError) as exc:
        dependency(request=request, provider=provider)
    
    assert "not found" in str(exc.value)
    assert exc.value.details["details"]["service_type"] == "TestService"
    assert exc.value.details["details"]["request_id"] == "test-request-id"

def test_get_service_error(request, provider):
    """Test get_service dependency error."""
    # Create dependency
    dependency = get_service(TestService)
    
    # Mock provider.get to raise error
    def mock_get(*args):
        raise ValueError("Test error")
    provider.get = mock_get
    
    # Try to get service
    with pytest.raises(DependencyError) as exc:
        dependency(request=request, provider=provider)
    
    assert "Failed to get service" in str(exc.value)
    assert exc.value.details["details"]["error"] == "Test error"
    assert exc.value.details["details"]["service_type"] == "TestService"
    assert exc.value.details["details"]["request_id"] == "test-request-id"

def test_database_service_dep(request, provider):
    """Test DatabaseServiceDep."""
    from backend.src.services.database import DatabaseService
    
    # Register database service
    service = DatabaseService()
    provider.register(DatabaseService, service)
    
    # Create dependency
    dependency = get_service(DatabaseService)
    
    # Get service
    result = dependency(request=request, provider=provider)
    assert result is service

def test_storage_service_dep(request, provider):
    """Test StorageServiceDep."""
    from backend.src.services.storage import StorageService
    
    # Register storage service
    service = StorageService()
    provider.register(StorageService, service)
    
    # Create dependency
    dependency = get_service(StorageService)
    
    # Get service
    result = dependency(request=request, provider=provider)
    assert result is service

def test_get_service_no_request_id(provider):
    """Test get_service dependency without request ID."""
    # Create request without request ID
    request = TestRequest()
    request.state.request_id = None
    
    # Create dependency
    dependency = get_service(TestService)
    
    # Try to get unregistered service
    with pytest.raises(DependencyError) as exc:
        dependency(request=request, provider=provider)
    
    assert "not found" in str(exc.value)
    assert exc.value.details["details"]["request_id"] is None
