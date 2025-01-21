import logging
import json
from datetime import datetime
from typing import Any
import sys
import threading
from pathlib import Path

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record as JSON"""
        # Base log data
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "thread": threading.current_thread().name,
            "message": record.getMessage(),
            "path": record.pathname,
            "line": record.lineno,
            "function": record.funcName
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": str(record.exc_info[0].__name__),
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)

def setup_logging(
    level: str = "INFO",
    log_file: str = None,
    json_format: bool = True
) -> None:
    """Setup application logging"""
    # Create logs directory if needed
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create handlers
    handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)

    # File handler if log file specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        handlers.append(file_handler)

    # Set formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Configure handlers
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)

class LogContext:
    """Context manager for adding fields to log records"""
    def __init__(self, **fields):
        self.fields = fields
        self.old_factory = logging.getLogRecordFactory()

    def record_factory(self, *args, **kwargs):
        record = self.old_factory(*args, **kwargs)
        record.extra_fields = getattr(record, 'extra_fields', {})
        record.extra_fields.update(self.fields)
        return record

    def __enter__(self):
        logging.setLogRecordFactory(self.record_factory)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)