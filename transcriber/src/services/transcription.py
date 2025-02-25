import torch
import whisperx
import time
import logging
from pyannote.audio import Pipeline
import ffmpeg
from pathlib import Path
import tempfile
import os
import zipfile
import asyncio
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple, Any
import numpy as np
from collections import deque
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_TOTAL,
    AUDIO_DURATION,
    WORD_COUNT,
    FOREIGN_SEGMENTS,
    MODEL_LOAD_TIME,
    GPU_MEMORY_USAGE,
    MODEL_INFERENCE_TIME,
    AUDIO_PROCESSING_TIME,
    track_time,
    track_gpu_memory,
    track_model_load_time,
    track_inference_time,
    track_audio_processing,
    count_words,
    track_foreign_segment
)

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "transcribo_secure"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @track_time(AUDIO_PROCESSING_TIME, {"operation": "process_zip"})
    async def process_zip(self, zip_path: str, job_id: str) -> Tuple[str, float]:
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)
        extract_dir = job_dir / "extracted"
        extract_dir.mkdir(exist_ok=True)

        total_duration = 0
        audio_files = []

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        for file in extract_dir.glob("**/*"):
            if file.is_file():
                try:
                    probe = await self._probe_file(str(file))
                    if any(s['codec_type'] == 'audio' for s in probe['streams']):
                        processed_file, duration = await self.process_audio(str(file), f"{job_id}_{len(audio_files)}")
                        audio_files.append(processed_file)
                        total_duration += duration
                except Exception as e:
                    logger.warning(f"Skipping {file}: {e}")

        if not audio_files:
            raise ValueError("No valid audio files in ZIP")

        output_path = str(job_dir / "merged.mp4")
        if len(audio_files) > 1:
            await self._merge_audio_files(audio_files, output_path)
        else:
            output_path = audio_files[0]

        return output_path, total_duration

    @track_time(AUDIO_PROCESSING_TIME, {"operation": "process_audio"})
    async def process_audio(self, input_path: str, job_id: str) -> Tuple[str, float]:
        job_dir = self.temp_dir / job_id
        job_dir.mkdir(exist_ok=True)
        output_path = str(job_dir / "processed.mp4")

        probe = await self._probe_file(input_path)
        duration = float(probe['format']['duration'])
        
        filters = ["lowpass=3000", "highpass=200", "loudnorm"]
        has_video = any(s['codec_type'] == 'video' for s in probe['streams'])

        input_stream = ffmpeg.input(input_path)
        if has_video:
            video = input_stream.video.filter('scale', -2, 320)
            audio = input_stream.audio.filter_multi_output(filters)
            output = ffmpeg.output(video, audio, output_path, acodec='aac', vcodec='libx264')
        else:
            audio = input_stream.audio.filter_multi_output(filters)
            output = ffmpeg.output(audio, output_path, acodec='aac')

        await self._run_ffmpeg(output)
        return output_path, duration

    async def _probe_file(self, file_path: str) -> dict:
        try:
            return await asyncio.to_thread(ffmpeg.probe, file_path)
        except ffmpeg.Error as e:
            logger.error(f"FFprobe error: {e.stderr.decode()}")
            raise

    async def _run_ffmpeg(self, stream) -> None:
        try:
            await asyncio.to_thread(stream.run, capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    @track_time(AUDIO_PROCESSING_TIME, {"operation": "merge"})
    async def _merge_audio_files(self, audio_files: List[str], output_path: str):
        inputs = [ffmpeg.input(f) for f in audio_files]
        audio = ffmpeg.filter([i.audio for i in inputs], 'amix', inputs=len(inputs))
        output = ffmpeg.output(audio, output_path, acodec='aac')
        await self._run_ffmpeg(output)

    def cleanup(self, job_id: str):
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

class JobStats:
    def __init__(self, max_samples: int = 100):
        self.durations = deque(maxlen=max_samples)
        self.processing_times = deque(maxlen=max_samples)
        self.word_counts = deque(maxlen=max_samples)
        self.languages = {}

    def add_job(self, duration: float, processing_time: float, word_count: int, language: str):
        self.durations.append(duration)
        self.processing_times.append(processing_time)
        self.word_counts.append(word_count)
        if language not in self.languages:
            self.languages[language] = []
        self.languages[language].append((duration, processing_time))

    def estimate_time(self, duration: float, language: str) -> Dict[str, Any]:
        if not self.durations:
            return {
                "estimated_time": duration * 2,  # Default estimate
                "confidence": 0.5,
                "range": (duration, duration * 3)
            }

        # Language-specific estimation if available
        if language in self.languages and len(self.languages[language]) >= 5:
            lang_durations, lang_times = zip(*self.languages[language])
            ratio = np.mean([t/d for t, d in zip(lang_times, lang_durations)])
            confidence = min(len(self.languages[language]) / 20, 0.9)  # Max confidence of 0.9
        else:
            # Fallback to overall statistics
            ratio = np.mean([t/d for t, d in zip(self.processing_times, self.durations)])
            confidence = min(len(self.durations) / 20, 0.8)  # Max confidence of 0.8

        estimated_time = duration * ratio
        std_dev = np.std([t/d for t, d in zip(self.processing_times, self.durations)])
        
        return {
            "estimated_time": estimated_time,
            "confidence": confidence,
            "range": (
                max(estimated_time - std_dev * estimated_time, duration),
                estimated_time + std_dev * estimated_time
            )
        }

class TranscriptionService:
    def __init__(self, device: str = "cuda", batch_size: int = 32, hf_token: Optional[str] = None):
        self.device = device
        self.batch_size = batch_size
        self.hf_token = hf_token
        self.audio_processor = AudioProcessor()
        self.model = None
        self.diarize_model = None
        self.initialize_models()
        self.primary_languages = {'de', 'en', 'gsw'}
        self.stats = JobStats()
        self.model_cache = {}

    def initialize_models(self):
        try:
            start_time = time.time()
            logger.info("Loading Whisper model...")
            self.model = whisperx.load_model("large-v3", self.device, compute_type="float16")
            track_model_load_time("whisper", time.time() - start_time)
            
            start_time = time.time()
            logger.info("Loading diarization model...")
            # Initialize diarization pipeline with auth token
            # Debug token info
            token_len = len(self.hf_token) if self.hf_token else 0
            logger.info(f"HF token length: {token_len}")
            logger.info(f"HF token value: {self.hf_token[:5]}...{self.hf_token[-5:] if token_len > 10 else ''}")
            
            try:
                logger.info("Attempting to load diarization model...")
                if not self.hf_token:
                    raise ValueError("HF_AUTH_TOKEN is not set")
                
                logger.info(f"Using HF token starting with: {self.hf_token[:10]}...")
                try:
                    # First try to initialize the pipeline
                    pipeline = Pipeline.from_pretrained(
                        "pyannote/speaker-diarization-3.1",
                        use_auth_token=self.hf_token
                    )
                    
                    if pipeline is None:
                        raise ValueError("Pipeline initialization returned None")
                    
                    # If successful, move to device
                    logger.info("Successfully loaded diarization pipeline")
                    logger.info("Moving pipeline to device...")
                    
                    self.diarize_model = pipeline.to(torch.device(self.device))
                    logger.info("Successfully moved pipeline to device")
                    
                except Exception as download_error:
                    error_msg = str(download_error)
                    logger.error(f"Download error details: {error_msg}")
                    
                    if "Could not download" in error_msg:
                        raise ValueError(
                            "Could not download diarization model. Please:\n"
                            "1. Visit https://hf.co/pyannote/speaker-diarization-3.1\n"
                            "2. Accept the user conditions\n"
                            "3. Ensure your HF_AUTH_TOKEN has the required access"
                        )
                    elif "401 Client Error" in error_msg:
                        raise ValueError(
                            "Invalid HF_AUTH_TOKEN. Please check your token is correct."
                        )
                    elif "403 Client Error" in error_msg:
                        raise ValueError(
                            "Permission denied. Please ensure you have:\n"
                            "1. Accepted the user conditions at https://hf.co/pyannote/speaker-diarization-3.1\n"
                            "2. Granted your HF_AUTH_TOKEN access to this model"
                        )
                    else:
                        raise ValueError(f"Failed to initialize diarization model: {error_msg}")
                
            except Exception as e:
                logger.error(f"Failed to load diarization model: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                logger.error(f"Error args: {e.args}")
                raise ValueError(
                    "Failed to initialize diarization model. Please ensure you have:\n"
                    "1. A valid HF_AUTH_TOKEN environment variable set\n"
                    "2. Accepted the user conditions at https://hf.co/pyannote/speaker-diarization-3.1\n"
                    "3. Granted your token access to the model\n"
                    f"Error: {str(e)}"
                )
            track_model_load_time("diarization", time.time() - start_time)
            
            # Track initial GPU memory usage
            track_gpu_memory()
            
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            raise

    @track_time(TRANSCRIPTION_DURATION, {"status": "processing"})
    async def transcribe(
        self,
        audio_path: str,
        job_id: str,
        language: Optional[str] = None,
        vocabulary: Optional[List[str]] = None
    ) -> Dict:
        """
        Transcribe audio file with specified language and vocabulary.
        
        Args:
            audio_path: Path to audio file
            job_id: Job ID for tracking
            language: Target language code (e.g. 'de', 'en')
            vocabulary: List of vocabulary words to improve recognition
            
        Returns:
            Dict containing transcription results
        """
        try:
            start_time = time.time()

            # Process audio file
            if zipfile.is_zipfile(audio_path):
                processed_path, duration = await self.audio_processor.process_zip(audio_path, job_id)
            else:
                processed_path, duration = await self.audio_processor.process_audio(audio_path, job_id)

            AUDIO_DURATION.observe(duration)
            audio = whisperx.load_audio(processed_path)

            # Run transcription
            transcribe_start = time.time()
            
            # Prepare initial prompt from vocabulary
            initial_prompt = ""
            if vocabulary:
                initial_prompt = " ".join(vocabulary)
            
            # Cache alignment models per language
            target_lang = language or "de"
            if target_lang not in self.model_cache:
                logger.info(f"Loading alignment model for {target_lang}")
                model_a, metadata = whisperx.load_align_model(
                    language_code=target_lang,
                    device=self.device
                )
                self.model_cache[target_lang] = (model_a, metadata)
                # Limit cache size
                if len(self.model_cache) > 5:
                    oldest_lang = next(iter(self.model_cache))
                    del self.model_cache[oldest_lang]

            # Run transcription with specified language
            result = self.model.transcribe(
                audio, 
                batch_size=self.batch_size,
                language=target_lang,
                initial_prompt=initial_prompt,
                task="transcribe",  # Force transcription task
                beam_size=5  # Increase beam size for better accuracy
            )
            track_inference_time("transcribe", time.time() - transcribe_start)

            # Use cached alignment model
            align_start = time.time()
            model_a, metadata = self.model_cache[target_lang]
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )
            track_inference_time("align", time.time() - align_start)

            # Run diarization
            diarize_start = time.time()
            diarize_segments = self.diarize_model({
                "waveform": torch.from_numpy(audio).unsqueeze(0),
                "sample_rate": 16000
            })
            diarize_df = whisperx.diarize.segments_to_df(diarize_segments)
            result = whisperx.assign_word_speakers(diarize_df, result)
            track_inference_time("diarize", time.time() - diarize_start)

            # Track GPU memory after processing
            track_gpu_memory()

            # Process segments and update metrics
            total_words = 0
            segments_with_language = []
            
            for segment in result["segments"]:
                # Get audio for this segment
                start_sample = int(segment["start"] * 16000)
                end_sample = int(segment["end"] * 16000)
                segment_audio = audio[start_sample:end_sample]
                
                if len(segment_audio) > 0:
                    # Detect language for this segment
                    segment_mel = whisperx.audio.log_mel_spectrogram(segment_audio)
                    segment_mel = segment_mel.to(self.device)
                    
                    with torch.no_grad():
                        encoder_output = self.model.model.encoder(segment_mel.unsqueeze(0))
                        probs = self.model.model.decoder.detect_language(encoder_output)
                        detected_language = max(probs.items(), key=lambda x: x[1])[0]
                        confidence = probs[detected_language]
                        
                        # Add language info to segment
                        segment["language"] = detected_language
                        segment["language_confidence"] = float(confidence)
                        segment["is_foreign"] = detected_language not in self.primary_languages
                        
                        # Track metrics
                        if segment["is_foreign"]:
                            track_foreign_segment(detected_language)
                        
                        # Count words
                        words = count_words(segment["text"], detected_language)
                        total_words += words
                        segment["word_count"] = words
                        
                        segments_with_language.append(segment)

            # Update result with processed segments
            result["segments"] = segments_with_language
            
            # Calculate language distribution
            language_counts = {}
            for segment in segments_with_language:
                lang = segment["language"]
                language_counts[lang] = language_counts.get(lang, 0) + segment["word_count"]
            
            # Determine primary language
            primary_language = max(language_counts.items(), key=lambda x: x[1])[0]
            
            # Track success
            TRANSCRIPTION_TOTAL.labels(status="success").inc()
            process_time = time.time() - start_time

            # Update job statistics
            self.stats.add_job(duration, process_time, total_words, primary_language)

            # Return enriched result
            return {
                "segments": segments_with_language,
                "language": primary_language,
                "language_distribution": language_counts,
                "duration": process_time,
                "word_count": total_words,
                "completed_at": datetime.utcnow().isoformat(),
                "metadata": {
                    "target_language": language,
                    "vocabulary_size": len(vocabulary) if vocabulary else 0,
                    "audio_duration": duration,
                    "processing_time": process_time,
                    "words_per_second": total_words / duration if duration > 0 else 0,
                    "processing_ratio": process_time / duration if duration > 0 else 0
                }
            }

        except Exception as e:
            TRANSCRIPTION_TOTAL.labels(status="failure").inc()
            logger.error(
                "Transcription failed",
                extra={
                    "error": str(e),
                    "job_id": job_id,
                    "language": language,
                    "vocabulary_size": len(vocabulary) if vocabulary else 0
                }
            )
            raise
        finally:
            # Clean up temporary files
            self.audio_processor.cleanup(job_id)

    def estimate_processing_time(self, duration: float, language: str) -> Dict[str, Any]:
        """
        Estimate processing time for a given audio duration and language.
        Returns estimated time in seconds and confidence level.
        """
        return self.stats.estimate_time(duration, language)

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.diarize_model is not None

    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for monitoring and optimization.
        """
        if not self.stats.durations:
            return {
                "average_processing_ratio": None,
                "average_words_per_second": None,
                "language_stats": {},
                "confidence_level": 0
            }

        overall_ratio = np.mean([t/d for t, d in zip(self.stats.processing_times, self.stats.durations)])
        words_per_second = np.mean([w/d for w, d in zip(self.stats.word_counts, self.stats.durations)])

        language_stats = {}
        for lang, data in self.stats.languages.items():
            if data:
                durations, times = zip(*data)
                language_stats[lang] = {
                    "average_ratio": np.mean([t/d for t, d in zip(times, durations)]),
                    "sample_count": len(data)
                }

        return {
            "average_processing_ratio": overall_ratio,
            "average_words_per_second": words_per_second,
            "language_stats": language_stats,
            "confidence_level": min(len(self.stats.durations) / 20, 0.9)
        }
