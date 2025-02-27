"""Tests for base service class."""

import pytest
from datetime import datetime
from typing import List, Type

from backend.src.services.base import BaseService
from backend.src.utils.exceptions import ServiceError

# Test services
class TestService(BaseService):
    """Test service."""
    pass

class DependentService(BaseService):
    """Service with dependencies."""
    __dependencies__ = [TestService]

class InitializingService(BaseService):
    """Service with initialization."""
    
    def __init__(self):
        """Initialize service."""
        super().__init__()
        self.initialized_called = False
    
    async def _initialize(self):
        """Initialize service."""
        self.initialized_called = True

class FailingService(BaseService):
    """Service that fails to initialize."""
    
    async def _initialize(self):
        """Initialize service."""
        raise ValueError("Initialization failed")

class MultiDependentService(BaseService):
    """Service with multiple dependencies."""
    __dependencies__ = [TestService, DependentService]

def test_base_service_init():
    """Test base service initialization."""
    service = BaseService()
    assert service.config == {}
    assert not service.initialized
    assert len(service.get_dependencies()) == 0

def test_base_service_with_config():
    """Test base service with config."""
    config = {"key": "value"}
    service = BaseService(config)
    assert service.config == config

def test_service_dependencies():
    """Test service dependencies."""
    service = DependentService()
    deps = service.get_dependencies()
    assert len(deps) == 1
    assert TestService in deps

def test_add_dependency():
    """Test adding dependency."""
    service = BaseService()
    service.add_dependency(TestService)
    assert service.has_dependency(TestService)

def test_get_dependencies():
    """Test getting dependencies."""
    service = MultiDependentService()
    deps = service.get_dependencies()
    assert len(deps) == 2
    assert TestService in deps
    assert DependentService in deps

def test_has_dependency():
    """Test checking dependency."""
    service = DependentService()
    assert service.has_dependency(TestService)
    assert not service.has_dependency(BaseService)

@pytest.mark.asyncio
async def test_initialize():
    """Test service initialization."""
    service = InitializingService()
    assert not service.initialized
    assert not service.initialized_called
    
    await service.initialize()
    assert service.initialized
    assert service.initialized_called

@pytest.mark.asyncio
async def test_initialize_idempotent():
    """Test initialize is idempotent."""
    service = InitializingService()
    await service.initialize()
    initialized_called = service.initialized_called
    
    # Reset flag and call initialize again
    service.initialized_called = False
    await service.initialize()
    
    # Should not have called _initialize again
    assert not service.initialized_called
    assert service.initialized

@pytest.mark.asyncio
async def test_initialize_error():
    """Test initialization error."""
    service = FailingService()
    
    with pytest.raises(ServiceError) as exc:
        await service.initialize()
    
    assert not service.initialized
    assert "Failed to initialize service" in str(exc.value)
    assert exc.value.details["details"]["service"] == "FailingService"
    assert "Initialization failed" in exc.value.details["details"]["error"]

def test_str_representation():
    """Test string representation."""
    service = BaseService()
    assert str(service) == "BaseService(initialized=False)"
    
    # Add dependency and check repr
    service.add_dependency(TestService)
    expected_repr = "BaseService(initialized=False, dependencies=['TestService'])"
    assert repr(service) == expected_repr

def test_class_level_dependencies():
    """Test class-level dependency declarations."""
    # Single dependency
    service = DependentService()
    assert len(service.get_dependencies()) == 1
    assert TestService in service.get_dependencies()
    
    # Multiple dependencies
    service = MultiDependentService()
    assert len(service.get_dependencies()) == 2
    assert TestService in service.get_dependencies()
    assert DependentService in service.get_dependencies()

def test_empty_dependencies():
    """Test service with no dependencies."""
    service = TestService()
    assert len(service.get_dependencies()) == 0

def test_dependency_inheritance():
    """Test dependency inheritance."""
    class ChildService(DependentService):
        pass
    
    service = ChildService()
    assert len(service.get_dependencies()) == 1
    assert TestService in service.get_dependencies()

def test_dependency_override():
    """Test dependency override."""
    class ChildService(DependentService):
        __dependencies__ = [BaseService]  # Override parent dependencies
    
    service = ChildService()
    assert len(service.get_dependencies()) == 1
    assert BaseService in service.get_dependencies()
    assert TestService not in service.get_dependencies()

def test_invalid_dependencies():
    """Test invalid dependency declarations."""
    class InvalidService(BaseService):
        __dependencies__ = "not a list"
    
    service = InvalidService()
    assert len(service.get_dependencies()) == 0
