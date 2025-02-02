# tests/test_viewer_service.py
import pytest
from backend_api.src.services.viewer import ViewerService

def test_create_viewer_html():
    viewer = ViewerService()
    segments = [
        {"start": 0, "end": 5, "speaker": "Speaker1", "text": "Hello, world!"},
        {"start": 5, "end": 10, "speaker": "Speaker1", "text": "How are you?"}
    ]
    media_url = "https://example.com/media.mp4"
    html = viewer.create_viewer(segments, media_url, combine_speaker=True, encode_base64=False)
    
    # Check for the presence of key HTML elements.
    assert "<video" in html
    assert "Hello, world!" in html
    assert "How are you?" in html
    assert "Speaker1" in html
