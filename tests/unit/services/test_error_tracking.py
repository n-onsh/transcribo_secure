"""Tests for error tracking service."""

import pytest
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch

from src.services.error_tracking import ErrorTrackingService
from src.types import (
    ErrorSeverity,
    EnhancedErrorContext,
    RecoverySuggestion
)

@pytest.fixture
def error_tracking_service():
    """Create error tracking service instance."""
    settings = {
        'error_retention_days': 7,
        'max_tracked_errors': 1000,
        'cleanup_interval_hours': 24
    }
    return ErrorTrackingService(settings)

@pytest.fixture
def sample_error_context():
    """Create sample error context."""
    return EnhancedErrorContext(
        operation="test_operation",
        timestamp=datetime.utcnow(),
        severity=ErrorSeverity.ERROR,
        resource_id="test-resource",
        user_id="test-user",
        request_id="test-request",
        details={
            "error_type": "test_error",
            "message": "Test error message"
        },
        recovery_suggestions=[
            RecoverySuggestion(
                action="Test Action",
                description="Test Description"
            )
        ],
        error_category="test_category",
        is_retryable=True,
        retry_after=60
    )

@pytest.mark.asyncio
async def test_track_error(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test tracking an error."""
    # Track error
    await error_tracking_service.track_error(sample_error_context)
    
    # Verify error was tracked
    assert len(error_tracking_service.error_history) == 1
    assert error_tracking_service.error_counts["test_error"] == 1
    assert len(error_tracking_service.error_patterns["test_category"]) == 1

@pytest.mark.asyncio
async def test_cleanup_old_errors(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test cleaning up old errors."""
    # Add old error
    old_error = sample_error_context.copy()
    old_error.timestamp = datetime.utcnow() - timedelta(days=10)
    await error_tracking_service.track_error(old_error)
    
    # Add recent error
    recent_error = sample_error_context.copy()
    await error_tracking_service.track_error(recent_error)
    
    # Clean up old errors
    await error_tracking_service.cleanup_old_errors()
    
    # Verify only recent error remains
    assert len(error_tracking_service.error_history) == 1
    assert error_tracking_service.error_history[0].timestamp == recent_error.timestamp

@pytest.mark.asyncio
async def test_get_error_stats(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test getting error statistics."""
    # Track multiple errors
    await error_tracking_service.track_error(sample_error_context)
    
    error2 = sample_error_context.copy()
    error2.severity = ErrorSeverity.WARNING
    error2.details["error_type"] = "other_error"
    await error_tracking_service.track_error(error2)
    
    # Get stats
    stats = await error_tracking_service.get_error_stats()
    
    # Verify stats
    assert stats["total_errors"] == 2
    assert stats["error_counts"]["test_error"] == 1
    assert stats["error_counts"]["other_error"] == 1
    assert stats["error_categories"]["test_category"] == 2

@pytest.mark.asyncio
async def test_get_recent_errors(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test getting recent errors with filtering."""
    # Track multiple errors
    await error_tracking_service.track_error(sample_error_context)
    
    error2 = sample_error_context.copy()
    error2.severity = ErrorSeverity.WARNING
    error2.details["error_type"] = "other_error"
    await error_tracking_service.track_error(error2)
    
    # Get filtered errors
    errors = await error_tracking_service.get_recent_errors(
        error_type="test_error",
        severity=ErrorSeverity.ERROR
    )
    
    # Verify filtering
    assert len(errors) == 1
    assert errors[0].details["error_type"] == "test_error"
    assert errors[0].severity == ErrorSeverity.ERROR

@pytest.mark.asyncio
async def test_analyze_error_patterns(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test analyzing error patterns."""
    # Track multiple errors
    for _ in range(5):
        await error_tracking_service.track_error(sample_error_context)
        
        error2 = sample_error_context.copy()
        error2.details["error_type"] = "other_error"
        await error_tracking_service.track_error(error2)
    
    # Get patterns
    patterns = await error_tracking_service.analyze_error_patterns()
    
    # Verify patterns
    assert "test_error" in patterns["common_errors"]
    assert "other_error" in patterns["common_errors"]
    assert patterns["common_errors"]["test_error"] == 5
    assert patterns["common_errors"]["other_error"] == 5

@pytest.mark.asyncio
async def test_get_recovery_suggestions(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test getting recovery suggestions."""
    # Track error with successful recovery
    error = sample_error_context.copy()
    error.details["recovered"] = True
    await error_tracking_service.track_error(error)
    
    # Get suggestions
    suggestions = await error_tracking_service.get_recovery_suggestions(
        "test_error"
    )
    
    # Verify suggestions
    assert len(suggestions) == 1
    assert suggestions[0].action == "Test Action"
    assert suggestions[0].description == "Test Description"

@pytest.mark.asyncio
async def test_max_errors_limit(
    error_tracking_service: ErrorTrackingService,
    sample_error_context: EnhancedErrorContext
):
    """Test maximum errors limit."""
    # Track more than max errors
    error_tracking_service.max_errors = 2
    
    for i in range(5):
        error = sample_error_context.copy()
        error.details["error_type"] = f"error_{i}"
        await error_tracking_service.track_error(error)
    
    # Verify only max errors kept
    assert len(error_tracking_service.error_history) == 2
    assert error_tracking_service.error_history[-1].details["error_type"] == "error_4"

@pytest.mark.asyncio
async def test_cleanup_task(error_tracking_service: ErrorTrackingService):
    """Test cleanup task initialization."""
    # Initialize service
    await error_tracking_service._initialize_impl()
    
    # Verify cleanup task created
    assert error_tracking_service.cleanup_task is not None
    
    # Cleanup
    await error_tracking_service._cleanup_impl()
    
    # Verify cleanup task cancelled
    assert error_tracking_service.cleanup_task.cancelled()

@pytest.mark.asyncio
async def test_default_suggestions(error_tracking_service: ErrorTrackingService):
    """Test default recovery suggestions."""
    # Get suggestions for different error types
    storage_suggestions = error_tracking_service._get_default_suggestions("storage_error")
    validation_suggestions = error_tracking_service._get_default_suggestions("validation_error")
    transcription_suggestions = error_tracking_service._get_default_suggestions("transcription_error")
    
    # Verify storage suggestions
    assert len(storage_suggestions) == 2
    assert any(s.action == "Check Storage" for s in storage_suggestions)
    assert any(s.action == "Check Permissions" for s in storage_suggestions)
    
    # Verify validation suggestions
    assert len(validation_suggestions) == 2
    assert any(s.action == "Check File Format" for s in validation_suggestions)
    assert any(s.action == "Verify File Size" for s in validation_suggestions)
    
    # Verify transcription suggestions
    assert len(transcription_suggestions) == 2
    assert any(s.action == "Check Audio" for s in transcription_suggestions)
    assert any(s.action == "Try Different Language" for s in transcription_suggestions)
