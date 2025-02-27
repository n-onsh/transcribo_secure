"""Error tracking service."""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from collections import defaultdict
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    ERROR_COUNT,
    ERROR_SEVERITY,
    track_error
)
from ..types import ErrorSeverity, EnhancedErrorContext
from .base import BaseService

class ErrorTrackingService(BaseService):
    """Service for tracking and analyzing errors."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize error tracking service.
        
        Args:
            settings: Service configuration settings
        """
        super().__init__(settings)
        self.error_history: List[EnhancedErrorContext] = []
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.error_patterns: Dict[str, List[EnhancedErrorContext]] = defaultdict(list)
        self.retention_days = int(settings.get('error_retention_days', 7))
        self.max_errors = int(settings.get('max_tracked_errors', 1000))
        self.cleanup_interval = int(settings.get('cleanup_interval_hours', 24))
        self.cleanup_task = None

    async def _initialize_impl(self):
        """Initialize service implementation."""
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        log_info("Error tracking service initialized")

    async def _cleanup_impl(self):
        """Clean up service implementation."""
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        log_info("Error tracking service cleaned up")

    async def _cleanup_loop(self):
        """Periodically clean up old errors."""
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval * 3600)
                await self.cleanup_old_errors()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log_error(f"Error in cleanup loop: {str(e)}")
                await asyncio.sleep(60)  # Retry after a minute

    async def cleanup_old_errors(self):
        """Clean up errors older than retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        # Clean up error history
        self.error_history = [
            error for error in self.error_history
            if error.timestamp > cutoff_date
        ]
        
        # Clean up error patterns
        for category, errors in self.error_patterns.items():
            self.error_patterns[category] = [
                error for error in errors
                if error.timestamp > cutoff_date
            ]
        
        # Trim to max size if needed
        if len(self.error_history) > self.max_errors:
            self.error_history = self.error_history[-self.max_errors:]
            
        log_info(f"Cleaned up error history, retained {len(self.error_history)} errors")

    async def track_error(self, error_context: EnhancedErrorContext):
        """Track an error occurrence.
        
        Args:
            error_context: Error context to track
        """
        # Add to history
        self.error_history.append(error_context)
        
        # Update counts
        error_type = error_context.details.get("error_type", "unknown")
        self.error_counts[error_type] += 1
        
        # Track in patterns
        category = error_context.error_category or error_type
        self.error_patterns[category].append(error_context)
        
        # Update metrics
        ERROR_COUNT.labels(type=error_type).inc()
        ERROR_SEVERITY.labels(
            type=error_type,
            severity=error_context.severity
        ).inc()
        track_error(error_type, error_context.severity)
        
        log_info(f"Tracked error: {error_type}")

    async def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics.
        
        Returns:
            Error statistics including counts and patterns
        """
        return {
            "total_errors": len(self.error_history),
            "error_counts": dict(self.error_counts),
            "error_categories": {
                category: len(errors)
                for category, errors in self.error_patterns.items()
            },
            "severity_counts": {
                severity.value: len([
                    e for e in self.error_history
                    if e.severity == severity
                ])
                for severity in ErrorSeverity
            }
        }

    async def get_recent_errors(
        self,
        limit: int = 100,
        error_type: Optional[str] = None,
        severity: Optional[ErrorSeverity] = None
    ) -> List[EnhancedErrorContext]:
        """Get recent errors with optional filtering.
        
        Args:
            limit: Maximum number of errors to return
            error_type: Optional error type filter
            severity: Optional severity filter
            
        Returns:
            List of matching errors
        """
        filtered = self.error_history
        
        if error_type:
            filtered = [
                e for e in filtered
                if e.details.get("error_type") == error_type
            ]
            
        if severity:
            filtered = [
                e for e in filtered
                if e.severity == severity
            ]
            
        # Sort by timestamp (newest first)
        sorted_errors = sorted(
            filtered,
            key=lambda e: e.timestamp,
            reverse=True
        )
        
        return sorted_errors[:limit]

    async def analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze error patterns to identify common issues.
        
        Returns:
            Analysis results including common errors and patterns
        """
        results = {}
        
        # Find most common error types
        results["common_errors"] = {
            error_type: count
            for error_type, count in sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }
        
        # Find error spikes
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        recent_errors = [
            e for e in self.error_history
            if e.timestamp > hour_ago
        ]
        
        error_spikes = defaultdict(int)
        for error in recent_errors:
            error_type = error.details.get("error_type", "unknown")
            error_spikes[error_type] += 1
        
        results["error_spikes"] = {
            error_type: count
            for error_type, count in error_spikes.items()
            if count > 10  # Threshold for spike detection
        }
        
        # Calculate error rates
        total_time = (now - hour_ago).total_seconds()
        results["error_rates"] = {
            error_type: count / total_time
            for error_type, count in error_spikes.items()
        }
        
        # Find correlated errors
        correlated = defaultdict(list)
        for error in recent_errors:
            error_type = error.details.get("error_type", "unknown")
            timestamp = error.timestamp
            
            # Look for other errors within 5 minutes
            window_start = timestamp - timedelta(minutes=5)
            window_end = timestamp + timedelta(minutes=5)
            
            related = [
                e for e in recent_errors
                if window_start <= e.timestamp <= window_end
                and e.details.get("error_type") != error_type
            ]
            
            if related:
                correlated[error_type].extend([
                    e.details.get("error_type", "unknown")
                    for e in related
                ])
        
        results["correlated_errors"] = {
            error_type: list(set(related))
            for error_type, related in correlated.items()
        }
        
        return results

    async def get_recovery_suggestions(
        self,
        error_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[RecoverySuggestion]:
        """Get recovery suggestions for an error type.
        
        Args:
            error_type: Type of error to get suggestions for
            context: Optional error context
            
        Returns:
            List of recovery suggestions
        """
        # Get recent similar errors
        similar_errors = [
            e for e in self.error_history
            if e.details.get("error_type") == error_type
        ]
        
        # Find successful recovery patterns
        successful_recoveries = [
            e.recovery_suggestions
            for e in similar_errors
            if e.details.get("recovered") is True
        ]
        
        if successful_recoveries:
            # Return most common successful recovery suggestions
            flattened = [
                suggestion
                for recovery in successful_recoveries
                for suggestion in recovery
            ]
            
            # Count occurrences of each suggestion
            suggestion_counts = defaultdict(int)
            for suggestion in flattened:
                key = (suggestion.action, suggestion.description)
                suggestion_counts[key] += 1
            
            # Return top suggestions
            top_suggestions = sorted(
                suggestion_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            
            return [
                RecoverySuggestion(
                    action=action,
                    description=description
                )
                for (action, description), _ in top_suggestions
            ]
        
        # Fallback to default suggestions
        return self._get_default_suggestions(error_type, context)
    
    def _get_default_suggestions(
        self,
        error_type: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[RecoverySuggestion]:
        """Get default recovery suggestions for an error type.
        
        Args:
            error_type: Type of error to get suggestions for
            context: Optional error context
            
        Returns:
            List of default recovery suggestions
        """
        suggestions = []
        
        if error_type == "storage_error":
            suggestions.extend([
                RecoverySuggestion(
                    action="Check storage connection",
                    description="Verify storage service is accessible"
                ),
                RecoverySuggestion(
                    action="Verify file permissions",
                    description="Ensure proper access rights are set"
                )
            ])
        elif error_type == "validation_error":
            suggestions.extend([
                RecoverySuggestion(
                    action="Check file format",
                    description="Ensure file meets format requirements"
                ),
                RecoverySuggestion(
                    action="Verify file size",
                    description="Check if file size is within limits"
                )
            ])
        elif error_type == "transcription_error":
            suggestions.extend([
                RecoverySuggestion(
                    action="Check audio quality",
                    description="Ensure audio file is clear and properly formatted"
                ),
                RecoverySuggestion(
                    action="Try different language",
                    description="Verify correct language is selected"
                )
            ])
        
        return suggestions
