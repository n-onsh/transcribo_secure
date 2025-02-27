"""Tests for error handling decorators."""

import pytest
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

from backend.src.utils.decorators import (
    handle_errors,
    retry,
    fallback
)
from backend.src.utils.exceptions import (
    TranscriboError,
    ValidationError,
    ServiceUnavailableError
)
from backend.src.types import ErrorCode

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

async def validation_error_operation() -> None:
    """Test operation that raises validation error."""
    raise ValidationError("Invalid input")

class TestHandleErrors:
    """Tests for handle_errors decorator."""
    
    async def test_successful_operation(self):
        """Test successful operation."""
        # Create decorated function
        @handle_errors()
        async def test_func():
            return "success"
        
        # Execute function
        result = await test_func()
        
        # Check result
        assert result == "success"
    
    async def test_transcribo_error(self):
        """Test handling TranscriboError."""
        # Create decorated function
        @handle_errors()
        async def test_func():
            raise ValidationError("Invalid input")
        
        # Execute function and check error
        with pytest.raises(ValidationError) as exc:
            await test_func()
        
        # Check error details
        error = exc.value
        assert error.message == "Invalid input"
        assert error.code == ErrorCode.VALIDATION_ERROR
    
    async def test_http_exception(self):
        """Test handling HTTPException."""
        from fastapi import HTTPException
        
        # Create decorated function
        @handle_errors()
        async def test_func():
            raise HTTPException(status_code=404, detail="Not found")
        
        # Execute function and check error
        with pytest.raises(TranscriboError) as exc:
            await test_func()
        
        # Check error details
        error = exc.value
        assert error.message == "Not found"
        assert error.code == ErrorCode.NOT_FOUND
        assert error.details["details"]["status_code"] == 404
    
    async def test_unhandled_exception(self):
        """Test handling unhandled exception."""
        # Create decorated function
        @handle_errors()
        async def test_func():
            raise ValueError("Something went wrong")
        
        # Execute function and check error
        with pytest.raises(TranscriboError) as exc:
            await test_func()
        
        # Check error details
        error = exc.value
        assert error.message == "Something went wrong"
        assert error.code == ErrorCode.INTERNAL_ERROR
        assert "timestamp" in error.details
        assert "operation" in error.details
        assert "details" in error.details
    
    async def test_operation_name(self):
        """Test custom operation name."""
        # Create decorated function
        @handle_errors(operation="custom_operation")
        async def test_func():
            raise ValueError("Error")
        
        # Execute function and check error
        with pytest.raises(TranscriboError) as exc:
            await test_func()
        
        # Check error details
        error = exc.value
        assert error.details["operation"] == "custom_operation"
    
    async def test_error_types(self):
        """Test handling specific error types."""
        # Create decorated function
        @handle_errors(error_types=[ValueError])
        async def test_func():
            raise ValueError("Expected error")
        
        # Execute function and check error
        with pytest.raises(ValueError):
            await test_func()

class TestRetry:
    """Tests for retry decorator."""
    
    async def test_successful_operation(self):
        """Test successful operation."""
        # Create decorated function
        @retry()
        async def test_func():
            return "success"
        
        # Execute function
        result = await test_func()
        
        # Check result
        assert result == "success"
    
    async def test_retry_success(self):
        """Test retry succeeds eventually."""
        attempts = 0
        
        # Create test function
        async def test_func():
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise ConnectionError("Connection failed")
            return "success"
        
        # Create decorated function
        decorated = retry(
            max_retries=2,
            retry_delay=0.1
        )(test_func)
        
        # Execute function
        result = await decorated()
        
        # Check result
        assert result == "success"
        assert attempts == 2
    
    async def test_retry_failure(self):
        """Test retry fails after max attempts."""
        attempts = 0
        
        # Create test function
        async def test_func():
            nonlocal attempts
            attempts += 1
            raise ConnectionError("Connection failed")
        
        # Create decorated function
        decorated = retry(
            max_retries=2,
            retry_delay=0.1
        )(test_func)
        
        # Execute function and check error
        with pytest.raises(ServiceUnavailableError) as exc:
            await decorated()
        
        # Check attempts and error details
        assert attempts == 3  # Initial attempt + 2 retries
        error = exc.value
        assert error.message == "Operation test_func failed after 2 retries"
        assert error.details["details"]["retries"] == 2
        assert error.details["details"]["max_retries"] == 2
        assert "last_error" in error.details["details"]
    
    async def test_retry_non_retryable(self):
        """Test non-retryable exception."""
        # Create decorated function
        @retry(retryable_exceptions=[ConnectionError])
        async def test_func():
            raise ValueError("Not retryable")
        
        # Execute function and check error
        with pytest.raises(ValueError):
            await test_func()
    
    async def test_retry_backoff(self):
        """Test retry backoff timing."""
        attempts = []
        start_time = None
        
        # Create test function
        async def test_func():
            nonlocal start_time
            if start_time is None:
                start_time = datetime.utcnow()
            attempts.append(
                (datetime.utcnow() - start_time).total_seconds()
            )
            raise ConnectionError("Connection failed")
        
        # Create decorated function
        decorated = retry(
            max_retries=2,
            retry_delay=0.1,
            backoff_factor=2.0,
            jitter=False
        )(test_func)
        
        # Execute function
        with pytest.raises(ServiceUnavailableError):
            await decorated()
        
        # Check attempt timing
        assert len(attempts) == 3
        assert attempts[0] < 0.1  # First attempt immediate
        assert 0.1 <= attempts[1] <= 0.2  # First retry after 0.1s
        assert 0.3 <= attempts[2] <= 0.4  # Second retry after 0.2s

class TestFallback:
    """Tests for fallback decorator."""
    
    async def test_successful_operation(self):
        """Test successful operation."""
        # Create fallback function
        async def fallback_func():
            return "fallback"
        
        # Create decorated function
        @fallback(fallback_func)
        async def test_func():
            return "success"
        
        # Execute function
        result = await test_func()
        
        # Check result
        assert result == "success"
    
    async def test_fallback_called(self):
        """Test fallback is called on error."""
        # Create fallback function
        async def fallback_func():
            return "fallback"
        
        # Create decorated function
        @fallback(fallback_func)
        async def test_func():
            raise ValueError("Error")
        
        # Execute function
        result = await test_func()
        
        # Check result
        assert result == "fallback"
    
    async def test_specific_exceptions(self):
        """Test fallback for specific exceptions."""
        # Create fallback function
        async def fallback_func():
            return "fallback"
        
        # Create decorated function
        @fallback(fallback_func, exceptions=[ValueError])
        async def test_func():
            raise KeyError("Not handled")
        
        # Execute function and check error
        with pytest.raises(KeyError):
            await test_func()
    
    async def test_fallback_with_args(self):
        """Test fallback with arguments."""
        # Create fallback function
        async def fallback_func(arg1, arg2=None):
            return f"fallback: {arg1}, {arg2}"
        
        # Create decorated function
        @fallback(fallback_func)
        async def test_func(arg1, arg2=None):
            raise ValueError("Error")
        
        # Execute function
        result = await test_func("test", arg2="value")
        
        # Check result
        assert result == "fallback: test, value"
