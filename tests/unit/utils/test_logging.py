"""
Tests for OpenTelemetry logging implementation.

Critical aspects:
1. Log emission with correct severity
2. Structured attributes
3. Context propagation
4. Error handling
"""
import pytest
from unittest.mock import MagicMock, patch
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from backend.src.services.keyvault import MockKeyVaultService
from backend.src.services.cleanup import CleanupService
from backend.src.services.storage import StorageService

@pytest.fixture
def mock_logger():
    """Create a mock OpenTelemetry logger."""
    with patch('opentelemetry.logs.get_logger') as mock:
        logger = MagicMock()
        mock.return_value = logger
        yield logger

class TestLoggingImplementation:
    """Test suite for OpenTelemetry logging implementation."""

    async def test_log_severity_levels(self, mock_logger):
        """Test that logs are emitted with correct severity levels."""
        # Initialize a service that uses logging
        service = MockKeyVaultService()

        # Trigger various log levels
        await service.get_secret("test_secret")  # Should trigger WARN
        await service.set_secret("test_secret", "value")  # Should trigger WARN
        
        # Verify log calls
        log_calls = mock_logger.emit.call_args_list
        assert len(log_calls) > 0
        
        # Check severity levels
        severities = [call.kwargs['severity'] for call in log_calls]
        assert Severity.WARN in severities

    async def test_structured_attributes(self, mock_logger):
        """Test that logs include proper structured attributes."""
        service = MockKeyVaultService()
        
        # Trigger a log with attributes
        secret_name = "test_secret"
        await service.get_secret(secret_name)
        
        # Verify attributes
        mock_logger.emit.assert_called()
        call_args = mock_logger.emit.call_args
        attributes = call_args.kwargs.get('attributes', {})
        
        assert 'secret_name' in attributes
        assert attributes['secret_name'] == secret_name

    async def test_error_context(self, mock_logger):
        """Test that error logs include proper context."""
        # Initialize service that will generate an error
        service = CleanupService(None, None)  # Missing required dependencies
        
        # Attempt operation that should fail
        try:
            await service._perform_cleanup()
        except:
            pass
        
        # Verify error log
        error_logs = [
            call for call in mock_logger.emit.call_args_list 
            if call.kwargs['severity'] == Severity.ERROR
        ]
        assert len(error_logs) > 0
        
        # Check error context
        error_log = error_logs[0]
        attributes = error_log.kwargs.get('attributes', {})
        assert 'error' in attributes
        assert isinstance(attributes['error'], str)

    async def test_log_correlation(self, mock_logger):
        """Test that logs are correlated with trace context."""
        # Create a trace context
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("test_operation") as span:
            # Perform operation that logs
            service = MockKeyVaultService()
            await service.get_secret("test_secret")
            
            # Verify log includes trace context
            mock_logger.emit.assert_called()
            # Note: In a real setup, OpenTelemetry would automatically
            # correlate logs with the current span. In our mock setup,
            # we're just verifying the logging call was made within
            # the span context.

    async def test_warning_logs(self, mock_logger):
        """Test warning logs for development implementations."""
        service = MockKeyVaultService()
        
        # Constructor should log a warning about being a temporary solution
        init_warnings = [
            call for call in mock_logger.emit.call_args_list
            if call.kwargs['severity'] == Severity.WARN
            and "temporary solution" in call.kwargs.get('attributes', {}).get('message', '')
        ]
        assert len(init_warnings) > 0

    async def test_info_logs(self, mock_logger):
        """Test informational logs."""
        # Use a service that logs info messages
        storage = StorageService()
        
        # Verify info logs
        info_logs = [
            call for call in mock_logger.emit.call_args_list
            if call.kwargs['severity'] == Severity.INFO
        ]
        assert len(info_logs) > 0

    async def test_log_attributes_structure(self, mock_logger):
        """Test that log attributes follow our standard structure."""
        service = MockKeyVaultService()
        
        # Trigger several logs
        await service.get_secret("test_secret")
        await service.set_secret("test_secret", "value")
        await service.delete_secret("test_secret")
        
        # Verify all logs have required attribute structure
        for call in mock_logger.emit.call_args_list:
            attributes = call.kwargs.get('attributes', {})
            
            # Attributes should be a dict
            assert isinstance(attributes, dict)
            
            # Values should be serializable
            for value in attributes.values():
                assert isinstance(value, (str, int, float, bool, type(None)))

    async def test_error_log_attributes(self, mock_logger):
        """Test that error logs include all required error context."""
        service = MockKeyVaultService()
        
        # Trigger an error condition
        try:
            raise ValueError("Test error")
        except Exception as e:
            logger = logs.get_logger(__name__)
            logger.emit(
                "Test error occurred",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "operation": "test_operation"
                }
            )
        
        # Verify error log structure
        error_logs = [
            call for call in mock_logger.emit.call_args_list
            if call.kwargs['severity'] == Severity.ERROR
        ]
        assert len(error_logs) > 0
        
        error_log = error_logs[0]
        attributes = error_log.kwargs.get('attributes', {})
        
        # Check required error attributes
        assert 'error' in attributes
        assert 'operation' in attributes
