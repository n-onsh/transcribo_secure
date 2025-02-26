"""Transcriber utilities."""

import logging
from prometheus_client import start_http_server
import os

def setup_metrics():
    """Set up Prometheus metrics server."""
    try:
        metrics_port = int(os.getenv("METRICS_PORT", "8002"))
        start_http_server(metrics_port)
        logging.info(f"Prometheus metrics server started on port {metrics_port}")
    except Exception as e:
        logging.error(f"Failed to start metrics server: {str(e)}")
        raise
