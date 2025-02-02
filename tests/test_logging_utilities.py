# tests/test_logging_utilities.py
import logging
import json
import pytest
from backend_api.src.utils.logging import JSONFormatter, LogContext, get_logger

def test_json_formatter():
    logger = get_logger("test_logger")
    formatter = JSONFormatter()
    # Create a dummy LogRecord.
    record = logging.LogRecord(name="test_logger", level=logging.INFO, pathname="dummy.py", lineno=10, msg="Test message", args=(), exc_info=None)
    formatted = formatter.format(record)
    # Parse the output as JSON.
    parsed = json.loads(formatted)
    assert parsed["logger"] == "test_logger"
    assert parsed["message"] == "Test message"
    assert "timestamp" in parsed

def test_log_context():
    logger = get_logger("test_logger")
    original_factory = logging.getLogRecordFactory()
    with LogContext(request_id="123", user="test_user"):
        record = logger.makeRecord("test_logger", logging.INFO, "dummy.py", 20, "Log with context", None, None)
        assert "request_id" in record.extra_fields
        assert record.extra_fields["request_id"] == "123"
        assert record.extra_fields["user"] == "test_user"
    # Outside the context, extra fields should not be added.
    new_record = logger.makeRecord("test_logger", logging.INFO, "dummy.py", 20, "Log without context", None, None)
    # Either the attribute is missing or it is empty.
    assert not hasattr(new_record, "extra_fields") or new_record.extra_fields == {}
