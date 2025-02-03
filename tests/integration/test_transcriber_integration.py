# tests/integration/test_transcriber_integration.py
import os
import pytest
from transcriber.src.main import TranscriberService
import asyncio

@pytest.mark.asyncio
async def test_transcriber_model_initialization():
    # Only run this integration test if a valid HF token is provided.
    hf_token = os.getenv("HF_AUTH_TOKEN")
    if not hf_token or hf_token == "test_token":
        pytest.skip("Valid HF token not provided; skipping transcriber integration test.")
    service = TranscriberService()
    # Check that the models are loaded.
    assert service.model is not None
    assert service.diarize_model is not None
