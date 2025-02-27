# Error Handling System

## Overview

The error handling system provides a comprehensive solution for handling, tracking, and displaying errors across the application. It includes:

- Custom exceptions with standardized error codes and severity levels
- Error tracking service for monitoring and analysis
- Error handler middleware for consistent error responses
- Error toast component for user-friendly error display
- Metrics for tracking error patterns and system health

## Components

### 1. Custom Exceptions

All application exceptions inherit from `TranscriboError` and include:

- Error code
- Severity level
- Detailed error context
- Recovery suggestions
- Retry information

Example:
```python
try:
    await storage.upload_file(file)
except StorageError as e:
    # Error includes retry information
    if e.is_retryable:
        await retry_operation(e.retry_after)
```

### 2. Error Tracking Service

The `ErrorTrackingService` provides:

- Error history tracking
- Pattern analysis
- Recovery suggestions
- Automatic cleanup of old errors

Example:
```python
error_tracking = ErrorTrackingService(settings)
await error_tracking.track_error(error_context)
patterns = await error_tracking.analyze_error_patterns()
```

### 3. Error Handler Middleware

The `ErrorHandlerMiddleware` ensures:

- Consistent error responses
- Error tracking integration
- Recovery suggestions
- Request context preservation

Example:
```python
app.add_middleware(
    ErrorHandlerMiddleware,
    error_tracking_service=error_tracking
)
```

### 4. Error Toast Component

The frontend error toast component provides:

- Severity-based styling
- Recovery suggestions
- Retry functionality
- Error details expansion

Example:
```python
error_toast = ErrorToastComponent()
await error_toast.render(request, errors=[error])
```

## Error Codes

| Code | Description | Severity | Retryable |
|------|-------------|----------|-----------|
| INTERNAL_ERROR | Internal server error | ERROR | No |
| VALIDATION_ERROR | Input validation failed | WARNING | No |
| AUTHENTICATION_ERROR | Authentication failed | ERROR | No |
| AUTHORIZATION_ERROR | Authorization failed | ERROR | No |
| RESOURCE_NOT_FOUND | Resource not found | WARNING | No |
| STORAGE_ERROR | Storage service error | ERROR | Yes |
| TRANSCRIPTION_ERROR | Transcription failed | ERROR | Yes |
| DATABASE_ERROR | Database error | ERROR | Yes |
| ZIP_ERROR | ZIP file error | WARNING | No |
| ENCRYPTION_ERROR | Encryption failed | ERROR | No |
| KEY_MANAGEMENT_ERROR | Key management error | ERROR | Yes |
| QUOTA_EXCEEDED | Quota limit reached | WARNING | Yes* |
| TOKEN_EXPIRED | Token expired | ERROR | No |
| TOKEN_INVALID | Token invalid | ERROR | No |
| TOKEN_MISSING | Token missing | ERROR | No |

\* Retryable if retry_after is provided

## Metrics

The system tracks various error-related metrics:

### Error Metrics
- Total error count by type
- Error severity distribution
- Retry attempts
- Recovery time

### Resource Metrics
- Memory usage
- CPU usage
- Storage usage

### Operation Metrics
- Operation duration
- Success/failure rates
- Queue sizes
- Job status

## Best Practices

### 1. Error Creation

Always provide detailed context:
```python
raise StorageError(
    message="Failed to upload file",
    details={
        "file_name": file.name,
        "size": file.size
    },
    is_retryable=True,
    retry_after=60
)
```

### 2. Error Handling

Handle errors at appropriate levels:
```python
try:
    result = await process_file(file)
except ValidationError as e:
    # Handle validation errors
    return {"error": str(e)}
except StorageError as e:
    # Handle storage errors with retry
    if e.is_retryable:
        return await retry_with_backoff(process_file, file)
    raise
except TranscriboError as e:
    # Handle other known errors
    log_error(e)
    raise
```

### 3. Recovery Suggestions

Provide actionable suggestions:
```python
RecoverySuggestion(
    action="Check File Format",
    description="Ensure file is a supported audio format",
    code_example="Supported formats: .mp3, .wav, .m4a"
)
```

### 4. Metrics Usage

Track important metrics:
```python
# Track error occurrence
track_error("validation_error", "warning")

# Track operation result
track_operation_result("file_upload", success=True)

# Track resource usage
track_memory_usage("heap", bytes_used)
```

## Integration Example

Complete example of error handling integration:

```python
from src.utils.exceptions import StorageError
from src.utils.metrics import track_error, track_operation_result
from src.types import RecoverySuggestion

async def upload_file(file):
    try:
        # Track operation start
        start_time = time.time()
        
        # Attempt upload
        result = await storage.upload(file)
        
        # Track success
        duration = time.time() - start_time
        track_operation_duration("upload", duration)
        track_operation_result("upload", True)
        
        return result
        
    except StorageError as e:
        # Track error
        track_error("storage_error", e.severity)
        
        # Add recovery suggestions
        e.recovery_suggestions.append(
            RecoverySuggestion(
                action="Check Storage",
                description="Verify storage service is accessible"
            )
        )
        
        # Track failure
        track_operation_result("upload", False)
        
        # Retry if possible
        if e.is_retryable:
            return await retry_with_backoff(upload_file, file)
            
        raise
```

## Testing

The error handling system includes comprehensive tests:

- Unit tests for all error types
- Integration tests for error handling flows
- Metrics tracking verification
- Recovery suggestion testing

Example test:
```python
def test_storage_error():
    error = StorageError(
        message="Storage unavailable",
        details={"service": "minio"},
        is_retryable=True,
        retry_after=60
    )
    
    assert error.code == ErrorCode.STORAGE_ERROR
    assert error.severity == ErrorSeverity.ERROR
    assert error.is_retryable
    assert error.retry_after == 60
