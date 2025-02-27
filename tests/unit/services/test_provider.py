"""Tests for service provider."""

import pytest
from datetime import datetime
from typing import List, Set, Optional

from backend.src.services.provider import ServiceProvider, ServiceLifetime
from backend.src.services.base import BaseService
from backend.src.utils.exceptions import DependencyError

# Test services
class TestService(BaseService):
    """Test service."""
    pass

class DependentService(BaseService):
    """Service with dependencies."""
    __dependencies__ = [TestService]

class CircularService1(BaseService):
    """Service with circular dependency."""
    __dependencies__ = ["CircularService2"]  # Forward reference

class CircularService2(BaseService):
    """Service with circular dependency."""
    __dependencies__ = [CircularService1]

class MultiDependentService(BaseService):
    """Service with multiple dependencies."""
    __dependencies__ = [TestService, DependentService]

@pytest.fixture
def provider() -> ServiceProvider:
    """Get service provider for testing."""
    provider = ServiceProvider()
    provider._initialized = False  # Reset for testing
    provider.__init__()
    return provider

def test_singleton():
    """Test service provider is singleton."""
    provider1 = ServiceProvider()
    provider2 = ServiceProvider()
    assert provider1 is provider2

def test_register_service(provider: ServiceProvider):
    """Test registering service."""
    service = TestService()
    provider.register(TestService, service)
    assert provider.get(TestService) is service

def test_get_unregistered_service(provider: ServiceProvider):
    """Test getting unregistered service."""
    with pytest.raises(DependencyError) as exc:
        provider.get(TestService)
    
    assert "not registered" in str(exc.value)
    assert exc.value.details["details"]["service_type"] == "TestService"

def test_service_dependencies(provider: ServiceProvider):
    """Test service with dependencies."""
    # Register dependency first
    test_service = TestService()
    provider.register(TestService, test_service)
    
    # Register dependent service
    dependent_service = DependentService()
    provider.register(DependentService, dependent_service)
    
    # Get service
    service = provider.get(DependentService)
    assert service is dependent_service

def test_missing_dependency(provider: ServiceProvider):
    """Test service with missing dependency."""
    # Register dependent service without dependency
    dependent_service = DependentService()
    provider.register(DependentService, dependent_service)
    
    # Try to get service
    with pytest.raises(DependencyError) as exc:
        provider.get(DependentService)
    
    assert "Missing dependency" in str(exc.value)
    assert exc.value.details["details"]["missing_dependency"] == "TestService"

def test_circular_dependency_detection(provider: ServiceProvider):
    """Test circular dependency detection."""
    # Register services with circular dependency
    service1 = CircularService1()
    service2 = CircularService2()
    
    # Should log warning but not fail
    provider.register(CircularService1, service1)
    provider.register(CircularService2, service2)
    
    # Services should still be registered
    assert provider.get(CircularService1) is service1
    assert provider.get(CircularService2) is service2

def test_multiple_dependencies(provider: ServiceProvider):
    """Test service with multiple dependencies."""
    # Register dependencies
    test_service = TestService()
    provider.register(TestService, test_service)
    
    dependent_service = DependentService()
    provider.register(DependentService, dependent_service)
    
    # Register service with multiple dependencies
    multi_service = MultiDependentService()
    provider.register(MultiDependentService, multi_service)
    
    # Get service
    service = provider.get(MultiDependentService)
    assert service is multi_service

def test_error_context(provider: ServiceProvider):
    """Test error context in exceptions."""
    with pytest.raises(DependencyError) as exc:
        provider.get(TestService)
    
    error_context = exc.value.details
    assert "timestamp" in error_context
    assert "operation" in error_context
    assert error_context["operation"] == "get_service"
    assert "details" in error_context
    assert error_context["details"]["service_type"] == "TestService"
    assert "registered_services" in error_context["details"]

def test_service_lifetime_enum():
    """Test ServiceLifetime enum."""
    assert ServiceLifetime.SINGLETON == "singleton"
    assert ServiceLifetime.SCOPED == "scoped"
    assert ServiceLifetime.TRANSIENT == "transient"
    
    assert list(ServiceLifetime) == [
        ServiceLifetime.SINGLETON,
        ServiceLifetime.SCOPED,
        ServiceLifetime.TRANSIENT
    ]
