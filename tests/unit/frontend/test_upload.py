"""Tests for upload component."""

import pytest
from unittest.mock import Mock
from fastapi import Request
from fastapi.templating import Jinja2Templates

from frontend.src.components.upload import UploadComponent

@pytest.fixture
def upload_component():
    """Create upload component."""
    return UploadComponent()

@pytest.fixture
def mock_request():
    """Create mock request."""
    return Mock(spec=Request)

def test_get_language_info(upload_component):
    """Test getting language information."""
    # Test valid language
    info = upload_component.get_language_info("de")
    assert info is not None
    assert info["code"] == "de"
    assert info["name"] == "German"
    assert "Hochdeutsch" in info["description"]
    
    # Test invalid language
    info = upload_component.get_language_info("invalid")
    assert info is None

def test_validate_file_size(upload_component):
    """Test file size validation."""
    # Test valid single file
    errors = upload_component.validate_file(
        file_name="test.mp3",
        file_size=500 * 1024 * 1024,  # 500MB
        is_zip=False
    )
    assert len(errors) == 0
    
    # Test invalid single file size
    errors = upload_component.validate_file(
        file_name="test.mp3",
        file_size=2 * 1024 * 1024 * 1024,  # 2GB
        is_zip=False
    )
    assert len(errors) == 1
    assert "too large" in errors[0].lower()
    
    # Test valid ZIP file
    errors = upload_component.validate_file(
        file_name="test.zip",
        file_size=1.5 * 1024 * 1024 * 1024,  # 1.5GB
        is_zip=True
    )
    assert len(errors) == 0
    
    # Test invalid ZIP file size
    errors = upload_component.validate_file(
        file_name="test.zip",
        file_size=3 * 1024 * 1024 * 1024,  # 3GB
        is_zip=True
    )
    assert len(errors) == 1
    assert "too large" in errors[0].lower()

def test_validate_file_type(upload_component):
    """Test file type validation."""
    # Test valid single file type
    errors = upload_component.validate_file(
        file_name="test.mp3",
        file_size=1024,
        is_zip=False
    )
    assert len(errors) == 0
    
    # Test invalid single file type
    errors = upload_component.validate_file(
        file_name="test.txt",
        file_size=1024,
        is_zip=False
    )
    assert len(errors) == 1
    assert "invalid file type" in errors[0].lower()
    
    # Test valid ZIP file type
    errors = upload_component.validate_file(
        file_name="test.zip",
        file_size=1024,
        is_zip=True
    )
    assert len(errors) == 0
    
    # Test invalid ZIP file type
    errors = upload_component.validate_file(
        file_name="test.rar",
        file_size=1024,
        is_zip=True
    )
    assert len(errors) == 1
    assert "invalid file type" in errors[0].lower()

def test_get_help_text(upload_component):
    """Test getting help text."""
    # Test valid topics
    assert "language" in upload_component.get_help_text("language").lower()
    assert "mp3" in upload_component.get_help_text("file_types").lower()
    assert "zip" in upload_component.get_help_text("batch_upload").lower()
    assert "duration" in upload_component.get_help_text("processing_time").lower()
    
    # Test invalid topic
    assert upload_component.get_help_text("invalid") == ""

@pytest.mark.asyncio
async def test_render(upload_component, mock_request):
    """Test rendering component."""
    # Test default render
    response = await upload_component.render(mock_request)
    assert response.status_code == 200
    assert response.template.name == "upload.html"
    
    # Test with selected language
    response = await upload_component.render(
        request=mock_request,
        selected_language="de"
    )
    assert response.status_code == 200
    assert response.template.name == "upload.html"
    
    # Test with errors
    response = await upload_component.render(
        request=mock_request,
        errors={"file": "Invalid file"}
    )
    assert response.status_code == 200
    assert response.template.name == "upload.html"

def test_validation_rules(upload_component):
    """Test validation rules."""
    # Check single file rules
    single_rules = upload_component.validation_rules["single_file"]
    assert single_rules["max_size"] == 1024 * 1024 * 1024  # 1GB
    assert ".mp3" in single_rules["types"]
    assert ".wav" in single_rules["types"]
    assert ".m4a" in single_rules["types"]
    
    # Check ZIP file rules
    zip_rules = upload_component.validation_rules["zip_file"]
    assert zip_rules["max_size"] == 2 * 1024 * 1024 * 1024  # 2GB
    assert zip_rules["max_files"] == 100
    assert ".zip" in zip_rules["types"]

def test_supported_languages(upload_component):
    """Test supported languages."""
    languages = upload_component.supported_languages
    
    # Check German
    de = next(l for l in languages if l["code"] == "de")
    assert de["name"] == "German"
    assert "Hochdeutsch" in de["description"]
    
    # Check English
    en = next(l for l in languages if l["code"] == "en")
    assert en["name"] == "English"
    assert "US/UK" in en["description"]
    
    # Check French
    fr = next(l for l in languages if l["code"] == "fr")
    assert fr["name"] == "French"
    assert "Standard" in fr["description"]
    
    # Check Italian
    it = next(l for l in languages if l["code"] == "it")
    assert it["name"] == "Italian"
    assert "Standard" in it["description"]

def test_file_types(upload_component):
    """Test file type information."""
    file_types = upload_component.file_types
    
    # Check MP3
    mp3 = next(t for t in file_types if t["extension"] == ".mp3")
    assert "recommended" in mp3["description"].lower()
    
    # Check WAV
    wav = next(t for t in file_types if t["extension"] == ".wav")
    assert "large" in wav["description"].lower()
    
    # Check M4A
    m4a = next(t for t in file_types if t["extension"] == ".m4a")
    assert "apple" in m4a["description"].lower()
    
    # Check ZIP
    zip_type = next(t for t in file_types if t["extension"] == ".zip")
    assert "multiple" in zip_type["description"].lower()
