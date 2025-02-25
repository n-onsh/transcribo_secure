import pytest
import torch
import numpy as np
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch
from transcriber.src.services.transcription import TranscriptionService, JobStats

@pytest.fixture
def job_stats():
    """Create JobStats instance"""
    return JobStats(max_samples=100)

@pytest.fixture
def transcription_service():
    """Create TranscriptionService with mocked models"""
    with patch('whisperx.load_model'), \
         patch('pyannote.audio.Pipeline'):
        service = TranscriptionService(device="cpu", batch_size=16)
        service.model = Mock()
        service.diarize_model = Mock()
        return service

def test_job_stats_initialization(job_stats):
    """Test JobStats initialization"""
    assert len(job_stats.durations) == 0
    assert len(job_stats.processing_times) == 0
    assert len(job_stats.word_counts) == 0
    assert len(job_stats.languages) == 0

def test_job_stats_add_job(job_stats):
    """Test adding job statistics"""
    # Add sample job
    job_stats.add_job(
        duration=300.0,  # 5 minutes
        processing_time=600.0,  # 10 minutes
        word_count=1000,
        language="de"
    )
    
    assert len(job_stats.durations) == 1
    assert len(job_stats.processing_times) == 1
    assert len(job_stats.word_counts) == 1
    assert len(job_stats.languages) == 1
    assert "de" in job_stats.languages
    assert len(job_stats.languages["de"]) == 1

def test_job_stats_max_samples(job_stats):
    """Test max samples limit"""
    # Add more than max_samples jobs
    for i in range(150):
        job_stats.add_job(
            duration=float(i),
            processing_time=float(i*2),
            word_count=i*100,
            language="de"
        )
    
    assert len(job_stats.durations) == 100  # Limited by max_samples
    assert len(job_stats.processing_times) == 100
    assert len(job_stats.word_counts) == 100

def test_job_stats_estimate_time(job_stats):
    """Test time estimation"""
    # Add sample jobs
    for i in range(10):
        job_stats.add_job(
            duration=300.0,  # 5 minutes
            processing_time=600.0,  # 10 minutes
            word_count=1000,
            language="de"
        )
    
    # Get estimate for similar job
    estimate = job_stats.estimate_time(300.0, "de")
    
    assert estimate["estimated_time"] == pytest.approx(600.0, rel=0.1)
    assert estimate["confidence"] > 0.0
    assert estimate["confidence"] <= 0.9  # Max confidence
    assert estimate["range"][0] <= estimate["estimated_time"]
    assert estimate["range"][1] >= estimate["estimated_time"]

def test_job_stats_language_specific_estimates(job_stats):
    """Test language-specific time estimates"""
    # Add jobs for different languages
    for i in range(10):
        # German jobs - 2x duration
        job_stats.add_job(
            duration=300.0,
            processing_time=600.0,
            word_count=1000,
            language="de"
        )
        # English jobs - 1.5x duration
        job_stats.add_job(
            duration=300.0,
            processing_time=450.0,
            word_count=1000,
            language="en"
        )
    
    # Get estimates for each language
    de_estimate = job_stats.estimate_time(300.0, "de")
    en_estimate = job_stats.estimate_time(300.0, "en")
    
    assert de_estimate["estimated_time"] > en_estimate["estimated_time"]
    assert de_estimate["confidence"] == en_estimate["confidence"]  # Same sample count

def test_job_stats_confidence_levels(job_stats):
    """Test confidence level calculation"""
    # Add increasing number of samples
    sample_counts = [1, 5, 10, 20]
    confidences = []
    
    for count in sample_counts:
        job_stats = JobStats()  # Fresh instance
        for i in range(count):
            job_stats.add_job(
                duration=300.0,
                processing_time=600.0,
                word_count=1000,
                language="de"
            )
        estimate = job_stats.estimate_time(300.0, "de")
        confidences.append(estimate["confidence"])
    
    # Confidence should increase with more samples
    assert all(c1 <= c2 for c1, c2 in zip(confidences, confidences[1:]))
    assert confidences[-1] <= 0.9  # Max confidence cap

def test_job_stats_unknown_language(job_stats):
    """Test estimation for unknown language"""
    # Add samples for known language
    for i in range(10):
        job_stats.add_job(
            duration=300.0,
            processing_time=600.0,
            word_count=1000,
            language="de"
        )
    
    # Get estimate for unknown language
    estimate = job_stats.estimate_time(300.0, "fr")
    
    # Should fall back to overall statistics
    assert estimate["estimated_time"] > 0
    assert estimate["confidence"] <= 0.8  # Lower confidence for fallback

def test_job_stats_no_samples(job_stats):
    """Test estimation with no samples"""
    estimate = job_stats.estimate_time(300.0, "de")
    
    # Should provide default estimate
    assert estimate["estimated_time"] == 600.0  # 2x duration
    assert estimate["confidence"] == 0.5
    assert estimate["range"] == (300.0, 900.0)  # 1x to 3x duration

def test_model_cache_management(transcription_service):
    """Test alignment model cache management"""
    # Mock alignment model loading
    mock_model = Mock()
    mock_metadata = Mock()
    
    with patch('whisperx.load_align_model', return_value=(mock_model, mock_metadata)):
        # Add models to cache
        for lang in ["de", "en", "fr", "it", "es", "nl"]:
            if lang not in transcription_service.model_cache:
                transcription_service.model_cache[lang] = (mock_model, mock_metadata)
    
    # Cache should be limited to 5 models
    assert len(transcription_service.model_cache) == 5
    
    # Adding another model should evict oldest
    transcription_service.model_cache["pt"] = (mock_model, mock_metadata)
    assert len(transcription_service.model_cache) == 5
    assert "de" not in transcription_service.model_cache  # First added should be evicted
