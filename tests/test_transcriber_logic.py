# tests/test_transcriber_logic.py
import os
import pytest
from pathlib import Path
from transcriber.src.main import Settings as TranscriberSettings, TranscriberService

def test_transcriber_settings_loading(monkeypatch):
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

def test_transcriber_cleanup(tmp_path):
    # Create a temporary directory structure for a job.
    temp_dir = tmp_path / "transcriber"
    temp_dir.mkdir()
    job_dir = temp_dir / "test_job"
    job_dir.mkdir()
    dummy_file = job_dir / "dummy.txt"
    dummy_file.write_text("temporary data")
    
    # Instantiate the TranscriberService and override its temp_dir.
    service = TranscriberService()
    service.temp_dir = temp_dir

    # Ensure the job directory exists.
    assert job_dir.exists()
    # Invoke cleanup for the job.
    service.audio_processor.cleanup("test_job")
    # Verify the job directory has been removed.
    assert not job_dir.exists()
