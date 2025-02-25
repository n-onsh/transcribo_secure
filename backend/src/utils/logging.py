"""Centralized logging utilities using OpenTelemetry"""

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

# Create tracer for logging
tracer = trace.get_tracer(__name__)

def log_error(error_msg: str, attributes: dict = None, span=None):
    """Log an error with OpenTelemetry tracing"""
    if span is None:
        span = trace.get_current_span()
    
    if attributes:
        span.set_attributes(attributes)
    span.set_attribute("error", error_msg)
    span.set_status(Status(StatusCode.ERROR))

def log_info(msg: str, attributes: dict = None, span=None):
    """Log info with OpenTelemetry tracing"""
    if span is None:
        span = trace.get_current_span()
    
    if attributes:
        span.set_attributes(attributes)
    span.set_attribute("message", msg)

def log_warning(msg: str, attributes: dict = None, span=None):
    """Log warning with OpenTelemetry tracing"""
    if span is None:
        span = trace.get_current_span()
    
    if attributes:
        span.set_attributes(attributes)
    span.set_attribute("warning", msg)
