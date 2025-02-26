"""Logging utilities."""

import logging
import json
from typing import Dict, Optional

def setup_logging():
    """Set up logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def log_info(msg: str, attrs: Optional[Dict] = None):
    """Log info message with attributes."""
    logger = logging.getLogger("transcribo")
    if attrs:
        msg = f"{msg} - {json.dumps(attrs)}"
    logger.info(msg)

def log_error(error_msg: str, attrs: Optional[Dict] = None):
    """Log error message with attributes."""
    logger = logging.getLogger("transcribo")
    if attrs:
        error_msg = f"{error_msg} - {json.dumps(attrs)}"
    logger.error(error_msg)

def log_warning(msg: str, attrs: Optional[Dict] = None):
    """Log warning message with attributes."""
    logger = logging.getLogger("transcribo")
    if attrs:
        msg = f"{msg} - {json.dumps(attrs)}"
    logger.warning(msg)
