import os
import pytest
from pathlib import Path
from transcriber.src.main import Settings as TranscriberSettings, TranscriberService
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

def test_transcriber_settings_loading(monkeypatch):
    monkeypatch.setenv("BACKEND_API_URL", "http://test-backend:8080")
    monkeypatch.setenv("POLL_INTERVAL", "7")
    monkeypatch.setenv("MAX_RETRIES", "2")
    monkeypatch.setenv("TEMP_DIR", "/tmp/test_transcriber")
    # Do not override HF_AUTH_TOKEN; it will be loaded from .env.
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

def test_transcriber_cleanup(tmp_path):
    temp_dir = tmp_path / "transcriber"
    temp_dir.mkdir()
    job_dir = temp_dir / "test_job"
    job_dir.mkdir()
    dummy_file = job_dir / "dummy.txt"
    dummy_file.write_text("temporary data")
    
    service = TranscriberService()
    service.temp_dir = temp_dir

    assert job_dir.exists()
    service.audio_processor.cleanup("test_job")
    assert not job_dir.exists()
