# tests/test_transcriber_config.py
import os
import pytest
from transcriber.src.main import Settings as TranscriberSettings

def test_transcriber_settings(monkeypatch):
    # Set test values for transcriber configuration.
    monkeypatch.setenv("BACKEND_API_URL", "http://test-backend:8080")
    monkeypatch.setenv("POLL_INTERVAL", "7")
    monkeypatch.setenv("MAX_RETRIES", "2")
    monkeypatch.setenv("TEMP_DIR", "/tmp/test_transcriber")
    monkeypatch.setenv("HF_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("DEVICE", "cpu")
    monkeypatch.setenv("BATCH_SIZE", "16")
    
    settings = TranscriberSettings()
    
    assert settings.BACKEND_API_URL == "http://test-backend:8080"
    assert settings.POLL_INTERVAL == 7
    assert settings.MAX_RETRIES == 2
    assert settings.TEMP_DIR == "/tmp/test_transcriber"
    assert settings.HF_AUTH_TOKEN == "test_token"
    assert settings.DEVICE == "cpu"
    assert settings.BATCH_SIZE == 16
