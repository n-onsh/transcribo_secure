# tests/test_frontend_config.py
import os
import pytest
from dotenv import load_dotenv

def test_frontend_env_loading(monkeypatch):
    # Set test environment variables for the frontend.
    monkeypatch.setenv("BACKEND_API_URL", "https://api.test.local")
    monkeypatch.setenv("FRONTEND_PORT", "8080")
    monkeypatch.setenv("REFRESH_INTERVAL", "10")
    
    # Load the .env file if your frontend uses python-dotenv.
    load_dotenv()
    
    # Get the environment variables.
    backend_url = os.getenv("BACKEND_API_URL")
    frontend_port = os.getenv("FRONTEND_PORT")
    refresh_interval = os.getenv("REFRESH_INTERVAL")
    
    # Assert that they match the test values.
    assert backend_url == "https://api.test.local"
    assert frontend_port == "8080"
    assert refresh_interval == "10"
