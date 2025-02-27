"""Tests for metrics utilities."""

import pytest
from unittest.mock import Mock, patch
from prometheus_client import Counter, Gauge, Histogram

from src.utils.metrics import (
    ERROR_COUNT,
    ERROR_SEVERITY,
    ERROR_RETRY_COUNT,
    ERROR_RECOVERY_TIME,
    MEMORY_USAGE,
    CPU_USAGE,
    STORAGE_USAGE,
    OPERATION_DURATION,
    OPERATION_FAILURES,
    OPERATION_SUCCESS,
    QUEUE_SIZE,
    QUEUE_LATENCY,
    JOB_DURATION,
    JOB_STATUS,
    track_error,
    track_error_retry,
    track_error_recovery,
    track_memory_usage,
    track_cpu_usage,
    track_storage_usage,
    track_operation_duration,
    track_operation_result,
    track_queue_size,
    track_queue_latency,
    track_job_duration,
    track_job_status,
    get_resource_metrics,
    get_error_metrics,
    get_operation_metrics,
    get_queue_metrics,
    get_job_metrics
)

@pytest.fixture
def mock_counter():
    """Create mock counter."""
    counter = Mock(spec=Counter)
    counter.labels.return_value = Mock()
    return counter

@pytest.fixture
def mock_gauge():
    """Create mock gauge."""
    gauge = Mock(spec=Gauge)
    gauge.labels.return_value = Mock()
    return gauge

@pytest.fixture
def mock_histogram():
    """Create mock histogram."""
    histogram = Mock(spec=Histogram)
    histogram.labels.return_value = Mock()
    return histogram

def test_track_error(mock_counter):
    """Test tracking error."""
    with patch('src.utils.metrics.ERROR_COUNT', mock_counter), \
         patch('src.utils.metrics.ERROR_SEVERITY', mock_counter):
        track_error("test_error", "error")
        
        ERROR_COUNT.labels.assert_called_once_with(type="test_error")
        ERROR_COUNT.labels().inc.assert_called_once()
        
        ERROR_SEVERITY.labels.assert_called_once_with(
            type="test_error",
            severity="error"
        )
        ERROR_SEVERITY.labels().inc.assert_called_once()

def test_track_error_retry(mock_counter):
    """Test tracking error retry."""
    with patch('src.utils.metrics.ERROR_RETRY_COUNT', mock_counter):
        track_error_retry("test_error")
        
        ERROR_RETRY_COUNT.labels.assert_called_once_with(type="test_error")
        ERROR_RETRY_COUNT.labels().inc.assert_called_once()

def test_track_error_recovery(mock_histogram):
    """Test tracking error recovery time."""
    with patch('src.utils.metrics.ERROR_RECOVERY_TIME', mock_histogram):
        track_error_recovery("test_error", 60.0)
        
        ERROR_RECOVERY_TIME.labels.assert_called_once_with(type="test_error")
        ERROR_RECOVERY_TIME.labels().observe.assert_called_once_with(60.0)

def test_track_memory_usage(mock_gauge):
    """Test tracking memory usage."""
    with patch('src.utils.metrics.MEMORY_USAGE', mock_gauge):
        track_memory_usage("heap", 1024)
        
        MEMORY_USAGE.labels.assert_called_once_with(type="heap")
        MEMORY_USAGE.labels().set.assert_called_once_with(1024)

def test_track_cpu_usage(mock_gauge):
    """Test tracking CPU usage."""
    with patch('src.utils.metrics.CPU_USAGE', mock_gauge):
        track_cpu_usage("process", 50.0)
        
        CPU_USAGE.labels.assert_called_once_with(type="process")
        CPU_USAGE.labels().set.assert_called_once_with(50.0)

def test_track_storage_usage(mock_gauge):
    """Test tracking storage usage."""
    with patch('src.utils.metrics.STORAGE_USAGE', mock_gauge):
        track_storage_usage("disk", 1024)
        
        STORAGE_USAGE.labels.assert_called_once_with(type="disk")
        STORAGE_USAGE.labels().set.assert_called_once_with(1024)

def test_track_operation_duration(mock_histogram):
    """Test tracking operation duration."""
    with patch('src.utils.metrics.OPERATION_DURATION', mock_histogram):
        track_operation_duration("upload", 2.5)
        
        OPERATION_DURATION.labels.assert_called_once_with(operation="upload")
        OPERATION_DURATION.labels().observe.assert_called_once_with(2.5)

def test_track_operation_result_success(mock_counter):
    """Test tracking successful operation."""
    with patch('src.utils.metrics.OPERATION_SUCCESS', mock_counter), \
         patch('src.utils.metrics.OPERATION_FAILURES', mock_counter):
        track_operation_result("upload", True)
        
        OPERATION_SUCCESS.labels.assert_called_once_with(operation="upload")
        OPERATION_SUCCESS.labels().inc.assert_called_once()
        OPERATION_FAILURES.labels.assert_not_called()

def test_track_operation_result_failure(mock_counter):
    """Test tracking failed operation."""
    with patch('src.utils.metrics.OPERATION_SUCCESS', mock_counter), \
         patch('src.utils.metrics.OPERATION_FAILURES', mock_counter):
        track_operation_result("upload", False)
        
        OPERATION_FAILURES.labels.assert_called_once_with(operation="upload")
        OPERATION_FAILURES.labels().inc.assert_called_once()
        OPERATION_SUCCESS.labels.assert_not_called()

def test_track_queue_size(mock_gauge):
    """Test tracking queue size."""
    with patch('src.utils.metrics.QUEUE_SIZE', mock_gauge):
        track_queue_size("jobs", 10)
        
        QUEUE_SIZE.labels.assert_called_once_with(queue="jobs")
        QUEUE_SIZE.labels().set.assert_called_once_with(10)

def test_track_queue_latency(mock_histogram):
    """Test tracking queue latency."""
    with patch('src.utils.metrics.QUEUE_LATENCY', mock_histogram):
        track_queue_latency("jobs", 30.0)
        
        QUEUE_LATENCY.labels.assert_called_once_with(queue="jobs")
        QUEUE_LATENCY.labels().observe.assert_called_once_with(30.0)

def test_track_job_duration(mock_histogram):
    """Test tracking job duration."""
    with patch('src.utils.metrics.JOB_DURATION', mock_histogram):
        track_job_duration("transcription", 300.0)
        
        JOB_DURATION.labels.assert_called_once_with(type="transcription")
        JOB_DURATION.labels().observe.assert_called_once_with(300.0)

def test_track_job_status(mock_counter):
    """Test tracking job status."""
    with patch('src.utils.metrics.JOB_STATUS', mock_counter):
        track_job_status("transcription", "completed")
        
        JOB_STATUS.labels.assert_called_once_with(
            type="transcription",
            status="completed"
        )
        JOB_STATUS.labels().inc.assert_called_once()

def test_get_resource_metrics():
    """Test getting resource metrics."""
    mock_memory = Mock()
    mock_memory._metrics = [{"type": "heap"}]
    mock_memory.labels().get.return_value = 1024
    
    mock_cpu = Mock()
    mock_cpu._metrics = [{"type": "process"}]
    mock_cpu.labels().get.return_value = 50.0
    
    mock_storage = Mock()
    mock_storage._metrics = [{"type": "disk"}]
    mock_storage.labels().get.return_value = 2048
    
    with patch('src.utils.metrics.MEMORY_USAGE', mock_memory), \
         patch('src.utils.metrics.CPU_USAGE', mock_cpu), \
         patch('src.utils.metrics.STORAGE_USAGE', mock_storage):
        metrics = get_resource_metrics()
        
        assert metrics == {
            "memory": {"heap": 1024},
            "cpu": {"process": 50.0},
            "storage": {"disk": 2048}
        }

def test_get_error_metrics():
    """Test getting error metrics."""
    mock_count = Mock()
    mock_count._metrics = [{"type": "test_error"}]
    mock_count.labels().get.return_value = 5
    
    mock_severity = Mock()
    mock_severity._metrics = [{"type": "test_error", "severity": "error"}]
    mock_severity.labels().get.return_value = 3
    
    mock_retry = Mock()
    mock_retry._metrics = [{"type": "test_error"}]
    mock_retry.labels().get.return_value = 2
    
    with patch('src.utils.metrics.ERROR_COUNT', mock_count), \
         patch('src.utils.metrics.ERROR_SEVERITY', mock_severity), \
         patch('src.utils.metrics.ERROR_RETRY_COUNT', mock_retry):
        metrics = get_error_metrics()
        
        assert metrics == {
            "counts": {"test_error": 5},
            "severities": {"test_error_error": 3},
            "retries": {"test_error": 2}
        }

def test_get_operation_metrics():
    """Test getting operation metrics."""
    mock_duration = Mock()
    mock_duration._metrics = [{"operation": "upload"}]
    mock_duration.labels()._sum.get.return_value = 10.0
    
    mock_failures = Mock()
    mock_failures._metrics = [{"operation": "upload"}]
    mock_failures.labels().get.return_value = 2
    
    mock_success = Mock()
    mock_success._metrics = [{"operation": "upload"}]
    mock_success.labels().get.return_value = 8
    
    with patch('src.utils.metrics.OPERATION_DURATION', mock_duration), \
         patch('src.utils.metrics.OPERATION_FAILURES', mock_failures), \
         patch('src.utils.metrics.OPERATION_SUCCESS', mock_success):
        metrics = get_operation_metrics()
        
        assert metrics == {
            "durations": {"upload": 10.0},
            "failures": {"upload": 2},
            "successes": {"upload": 8}
        }

def test_get_queue_metrics():
    """Test getting queue metrics."""
    mock_size = Mock()
    mock_size._metrics = [{"queue": "jobs"}]
    mock_size.labels().get.return_value = 5
    
    mock_latency = Mock()
    mock_latency._metrics = [{"queue": "jobs"}]
    mock_latency.labels()._sum.get.return_value = 30.0
    
    with patch('src.utils.metrics.QUEUE_SIZE', mock_size), \
         patch('src.utils.metrics.QUEUE_LATENCY', mock_latency):
        metrics = get_queue_metrics()
        
        assert metrics == {
            "sizes": {"jobs": 5},
            "latencies": {"jobs": 30.0}
        }

def test_get_job_metrics():
    """Test getting job metrics."""
    mock_duration = Mock()
    mock_duration._metrics = [{"type": "transcription"}]
    mock_duration.labels()._sum.get.return_value = 300.0
    
    mock_status = Mock()
    mock_status._metrics = [{"type": "transcription", "status": "completed"}]
    mock_status.labels().get.return_value = 10
    
    with patch('src.utils.metrics.JOB_DURATION', mock_duration), \
         patch('src.utils.metrics.JOB_STATUS', mock_status):
        metrics = get_job_metrics()
        
        assert metrics == {
            "durations": {"transcription": 300.0},
            "statuses": {"transcription_completed": 10}
        }
