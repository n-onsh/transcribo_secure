"""Logging utilities for transcriber service."""

import logging
import json
import time
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('transcriber')

def _format_log_attrs(attrs: Optional[Dict[str, Any]] = None) -> str:
    """Format log attributes as JSON string."""
    if not attrs:
        return ""
    try:
        return json.dumps(attrs, default=str)
    except Exception:
        return str(attrs)

def log_info(message: str, **attrs):
    """Log info message with attributes."""
    formatted_attrs = _format_log_attrs(attrs)
    if formatted_attrs:
        logger.info(f"{message} {formatted_attrs}")
    else:
        logger.info(message)

def log_error(message: str, **attrs):
    """Log error message with attributes."""
    formatted_attrs = _format_log_attrs(attrs)
    if formatted_attrs:
        logger.error(f"{message} {formatted_attrs}")
    else:
        logger.error(message)

def log_warning(message: str, **attrs):
    """Log warning message with attributes."""
    formatted_attrs = _format_log_attrs(attrs)
    if formatted_attrs:
        logger.warning(f"{message} {formatted_attrs}")
    else:
        logger.warning(message)

def log_debug(message: str, **attrs):
    """Log debug message with attributes."""
    formatted_attrs = _format_log_attrs(attrs)
    if formatted_attrs:
        logger.debug(f"{message} {formatted_attrs}")
    else:
        logger.debug(message)
