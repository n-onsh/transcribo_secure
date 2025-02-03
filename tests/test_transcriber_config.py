import os
import pytest
from transcriber.src.main import Settings as TranscriberSettings
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

def test_transcriber_settings(monkeypatch):
    monkeypatch.setenv("BACKEND_API_URL", "http://test-backend:8080")
    monkeypatch.setenv("POLL_INTERVAL", "7")
    monkeypatch.setenv("MAX_RETRIES", "2")
    monkeypatch.setenv("TEMP_DIR", "/tmp/test_transcriber")
    # Do not override HF_AUTH_TOKEN; use the value from .env.
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("BATCH_SIZE", "16")
    
    settings = TranscriberSettings()
    
    assert settings.BACKEND_API_URL == "http://test-backend:8080"
    assert settings.POLL_INTERVAL == 7
    assert settings.MAX_RETRIES == 2
    assert settings.TEMP_DIR == "/tmp/test_transcriber"
    expected_hf_token = os.getenv("HF_AUTH_TOKEN")
    assert settings.HF_AUTH_TOKEN == expected_hf_token
    assert settings.DEVICE == "cpu"
    assert settings.BATCH_SIZE == 16
