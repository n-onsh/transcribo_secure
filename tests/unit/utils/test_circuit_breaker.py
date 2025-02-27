"""Tests for circuit breaker implementation."""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from backend.src.utils.circuit_breaker import (
    CircuitState,
    CircuitBreaker,
    CircuitBreakerRegistry,
    circuit_breaker
)
from backend.src.utils.exceptions import ServiceUnavailableError

# Test helpers
async def success_operation() -> str:
    """Test operation that succeeds."""
    return "success"

async def failing_operation() -> None:
    """Test operation that fails."""
    raise ValueError("Operation failed")

async def timeout_operation() -> None:
    """Test operation that times out."""
    await asyncio.sleep(2)
    return "timeout"

class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""
    
    @pytest.fixture
    def cb(self) -> CircuitBreaker:
        """Get circuit breaker for testing."""
        return CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1,
            timeout=1.0
        )
    
    async def test_successful_operation(self, cb: CircuitBreaker):
        """Test successful operation."""
        # Decorate function
        wrapped = cb(success_operation)
        
        # Execute operation
        result = await wrapped()
        
        # Check result
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 1
        assert cb.total_calls == 1
        assert cb.open_count == 0
        assert cb.last_success_time is not None
        assert cb.last_failure_time is None
    
    async def test_failing_operation(self, cb: CircuitBreaker):
        """Test failing operation."""
        # Decorate function
        wrapped = cb(failing_operation)
        
        # Execute operation and check error
        with pytest.raises(ServiceUnavailableError) as exc:
            await wrapped()
        
        # Check circuit breaker state
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1
        assert cb.success_count == 0
        assert cb.total_calls == 1
        assert cb.open_count == 0
        assert cb.last_success_time is None
        assert cb.last_failure_time is not None
        
        # Check error details
        error = exc.value
        assert error.message == "Service test failed: Operation failed"
        assert error.details["details"]["circuit"] == "test"
        assert error.details["details"]["state"] == "closed"
        assert error.details["details"]["failure_count"] == 1
    
    async def test_timeout_operation(self, cb: CircuitBreaker):
        """Test operation timeout."""
        # Decorate function
        wrapped = cb(timeout_operation)
        
        # Execute operation and check error
        with pytest.raises(ServiceUnavailableError) as exc:
            await wrapped()
        
        # Check circuit breaker state
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1
        assert cb.success_count == 0
        assert cb.total_calls == 1
        assert cb.open_count == 0
        assert cb.last_success_time is None
        assert cb.last_failure_time is not None
        
        # Check error details
        error = exc.value
        assert error.message == "Service test timed out after 1.0 seconds"
        assert error.details["details"]["circuit"] == "test"
        assert error.details["details"]["state"] == "closed"
        assert error.details["details"]["failure_count"] == 1
        assert error.details["details"]["timeout"] == 1.0
    
    async def test_circuit_opens_after_failures(self, cb: CircuitBreaker):
        """Test circuit opens after reaching failure threshold."""
        # Decorate function
        wrapped = cb(failing_operation)
        
        # Execute operation multiple times
        for i in range(3):
            with pytest.raises(ServiceUnavailableError):
                await wrapped()
        
        # Check circuit breaker state
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 2
        assert cb.success_count == 0
        assert cb.total_calls == 3
        assert cb.open_count == 1
        assert cb.last_success_time is None
        assert cb.last_failure_time is not None
    
    async def test_circuit_half_open_after_timeout(self, cb: CircuitBreaker):
        """Test circuit moves to half-open state after recovery timeout."""
        # Open circuit
        wrapped = cb(failing_operation)
        for i in range(2):
            with pytest.raises(ServiceUnavailableError):
                await wrapped()
        
        # Wait for recovery timeout
        await asyncio.sleep(1.1)
        
        # Execute successful operation
        wrapped = cb(success_operation)
        result = await wrapped()
        
        # Check circuit breaker state
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 1
        assert cb.total_calls == 3
        assert cb.open_count == 1
        assert cb.last_success_time is not None
    
    async def test_excluded_exceptions(self):
        """Test excluded exceptions don't count as failures."""
        # Create circuit breaker with excluded exception
        cb = CircuitBreaker(
            name="test",
            failure_threshold=2,
            excluded_exceptions=[ValueError]
        )
        
        # Create test function
        async def test_func():
            raise ValueError("Expected error")
        
        # Decorate function
        wrapped = cb(test_func)
        
        # Execute operation multiple times
        for i in range(3):
            with pytest.raises(ValueError):
                await wrapped()
        
        # Check circuit breaker state
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.total_calls == 3
        assert cb.open_count == 0
    
    async def test_get_status(self, cb: CircuitBreaker):
        """Test getting circuit breaker status."""
        # Execute some operations
        wrapped = cb(failing_operation)
        for i in range(2):
            with pytest.raises(ServiceUnavailableError):
                await wrapped()
        
        # Get status
        status = cb.get_status()
        
        # Check status
        assert status["name"] == "test"
        assert status["state"] == "open"
        assert status["failure_count"] == 2
        assert status["success_count"] == 0
        assert status["total_calls"] == 2
        assert status["open_count"] == 1
        assert status["failure_threshold"] == 2
        assert status["recovery_timeout"] == 1
        assert status["timeout"] == 1.0
        assert status["last_failure"] is not None
        assert status["last_success"] is None

class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""
    
    @pytest.fixture
    async def registry(self) -> CircuitBreakerRegistry:
        """Get circuit breaker registry for testing."""
        registry = CircuitBreakerRegistry()
        
        # Register some circuit breakers
        await registry.register(CircuitBreaker(name="cb1"))
        await registry.register(CircuitBreaker(name="cb2"))
        
        return registry
    
    async def test_register_circuit_breaker(self, registry: CircuitBreakerRegistry):
        """Test registering circuit breaker."""
        # Register new circuit breaker
        cb = CircuitBreaker(name="cb3")
        await registry.register(cb)
        
        # Get circuit breaker
        result = await registry.get("cb3")
        
        # Check result
        assert result is cb
    
    async def test_get_circuit_breaker(self, registry: CircuitBreakerRegistry):
        """Test getting circuit breaker."""
        # Get existing circuit breaker
        cb = await registry.get("cb1")
        
        # Check result
        assert cb is not None
        assert cb.name == "cb1"
        
        # Get non-existent circuit breaker
        cb = await registry.get("unknown")
        
        # Check result
        assert cb is None
    
    async def test_get_status(self, registry: CircuitBreakerRegistry):
        """Test getting circuit breaker status."""
        # Get status
        status = await registry.get_status()
        
        # Check status
        assert len(status) == 2
        assert "cb1" in status
        assert "cb2" in status
        assert status["cb1"]["name"] == "cb1"
        assert status["cb2"]["name"] == "cb2"

class TestCircuitBreakerDecorator:
    """Tests for circuit_breaker decorator."""
    
    async def test_decorator(self):
        """Test circuit breaker decorator."""
        # Create decorated function
        @circuit_breaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1,
            timeout=1.0
        )
        async def test_func():
            return "success"
        
        # Execute function
        result = await test_func()
        
        # Check result
        assert result == "success"
        
        # Get circuit breaker from registry
        cb = await circuit_breaker_registry.get("test")
        
        # Check circuit breaker state
        assert cb is not None
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 1
        assert cb.total_calls == 1
        assert cb.open_count == 0
