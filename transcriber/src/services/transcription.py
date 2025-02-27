"""Transcription service."""

import gc
import os
import io
import asyncio
import logging
import torch
import torchaudio
from typing import Dict, Optional, List, BinaryIO, Tuple
from contextlib import asynccontextmanager
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_ERRORS,
    MODEL_LOAD_TIME,
    MODEL_INFERENCE_TIME,
    MEMORY_USAGE,
    track_transcription,
    track_transcription_error,
    track_model_load,
    track_model_inference,
    track_memory_usage
)

class TranscriptionService:
    """Service for handling audio transcription."""

    def __init__(self, settings):
        """Initialize transcription service."""
        self.settings = settings
        self.initialized = False
        self.model = None
        self.model_lock = asyncio.Lock()
        self.processing_semaphore = asyncio.Semaphore(
            int(settings.get('max_concurrent_jobs', 2))
        )

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize transcription settings
            self.model_path = self.settings.get('model_path')
            self.device = self.settings.get('device', 'cpu')
            self.batch_size = int(self.settings.get('batch_size', 32))
            self.cache_dir = self.settings.get('cache_dir')
            self.chunk_size = int(self.settings.get('chunk_size', 30))  # seconds
            self.max_retries = int(self.settings.get('max_retries', 3))
            self.retry_delay = float(self.settings.get('retry_delay', 1.0))

            if not self.model_path:
                raise ValueError("Model path not configured")

            # Load model
            start_time = logging.time()
            async with self._model_context():
                self.model = await self._load_model()
            
            # Track model load time
            duration = logging.time() - start_time
            MODEL_LOAD_TIME.observe(duration)
            track_model_load(duration)

            self.initialized = True
            log_info("Transcription service initialized")

        except Exception as e:
            log_error(f"Failed to initialize transcription service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            if self.model:
                async with self._model_context():
                    await self._unload_model()
            self.initialized = False
            log_info("Transcription service cleaned up")

        except Exception as e:
            log_error(f"Error during transcription service cleanup: {str(e)}")
            raise

    @asynccontextmanager
    async def _model_context(self):
        """Context manager for model operations with memory management."""
        try:
            async with self.model_lock:
                # Track memory before
                memory_before = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
                MEMORY_USAGE.set(memory_before)
                track_memory_usage(memory_before)
                
                yield
                
                # Clear CUDA cache
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                
                # Force garbage collection
                gc.collect()
                
                # Track memory after
                memory_after = torch.cuda.memory_allocated() if torch.cuda.is_available() else 0
                MEMORY_USAGE.set(memory_after)
                track_memory_usage(memory_after)
        except Exception as e:
            log_error(f"Error in model context: {str(e)}")
            raise

    async def transcribe(
        self,
        audio_file: BinaryIO,
        job_id: str,
        language: str = 'de',
        vocabulary: Optional[List[str]] = None
    ) -> Dict:
        """Transcribe an audio file."""
        start_time = logging.time()
        try:
            # Acquire processing semaphore
            async with self.processing_semaphore:
                log_info(f"Starting transcription for job {job_id}")

                # Prepare audio in chunks
                chunks = await self._prepare_audio_chunks(audio_file)
                
                # Process chunks with retries
                results = []
                for i, chunk in enumerate(chunks):
                    for attempt in range(self.max_retries):
                        try:
                            # Run inference on chunk
                            async with self._model_context():
                                inference_start = logging.time()
                                chunk_result = await self._run_inference(
                                    chunk,
                                    language,
                                    vocabulary
                                )
                                
                                # Track inference time
                                inference_duration = logging.time() - inference_start
                                MODEL_INFERENCE_TIME.observe(inference_duration)
                                track_model_inference(inference_duration)
                                
                                results.append(chunk_result)
                                break
                        except Exception as e:
                            if attempt == self.max_retries - 1:
                                raise
                            log_warning(
                                f"Retry {attempt + 1} for chunk {i} of job {job_id}: {str(e)}"
                            )
                            await asyncio.sleep(self.retry_delay * (attempt + 1))
                
                # Combine results
                final_result = await self._combine_results(results)
                
                # Post-process
                final_result = await self._post_process(final_result)
                
                # Track total duration
                duration = logging.time() - start_time
                TRANSCRIPTION_DURATION.observe(duration)
                track_transcription(duration)
                
                log_info(f"Completed transcription for job {job_id} in {duration:.2f}s")
                return final_result

        except Exception as e:
            TRANSCRIPTION_ERRORS.inc()
            track_transcription_error()
            log_error(f"Error transcribing job {job_id}: {str(e)}")
            raise

    async def _load_model(self) -> Tuple:
        """Load the transcription model."""
        try:
            import whisperx
            from pyannote.audio import Pipeline
            
            # Determine compute type based on device
            compute_type = "float16" if self.device == "cuda" else "float32"
            
            # Load the Whisper model
            model = whisperx.load_model(
                "large-v3",  # Using Whisper v3 large model
                self.device,
                compute_type=compute_type,
                download_root=self.cache_dir
            )
            
            # Load the diarization model
            diarize_model = Pipeline.from_pretrained(
                "pyannote/speaker-diarization",
                use_auth_token=os.environ.get("HF_AUTH_TOKEN")
            ).to(torch.device(self.device))
            
            log_info(f"Models loaded successfully on {self.device}")
            return (model, diarize_model)
        except Exception as e:
            log_error(f"Error loading model: {str(e)}")
            raise

    async def _unload_model(self):
        """Unload the transcription model."""
        try:
            if self.model:
                # Explicitly delete model references
                self.model = None
                
                # Force garbage collection
                gc.collect()
                
                # Clear CUDA cache if available
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
        except Exception as e:
            log_error(f"Error unloading model: {str(e)}")
            raise

    async def _prepare_audio_chunks(self, audio_file: BinaryIO) -> List[bytes]:
        """Prepare audio in chunks for processing."""
        try:
            # Read file into memory buffer
            buffer = io.BytesIO(audio_file.read())
            audio_file.seek(0)
            
            # Load audio
            waveform, sample_rate = torchaudio.load(buffer)
            
            # Apply audio filtering (similar to the example's lowpass/highpass)
            # This is optional but can improve transcription quality
            if hasattr(torchaudio.transforms, 'Resample'):
                # Ensure consistent sample rate (16kHz is standard for Whisper)
                if sample_rate != 16000:
                    resampler = torchaudio.transforms.Resample(
                        orig_freq=sample_rate, new_freq=16000
                    )
                    waveform = resampler(waveform)
                    sample_rate = 16000
            
            # Calculate chunk size in samples
            chunk_samples = self.chunk_size * sample_rate
            
            # Split into chunks
            chunks = []
            for i in range(0, waveform.size(1), chunk_samples):
                chunk = waveform[:, i:i + chunk_samples]
                chunk_buffer = io.BytesIO()
                torchaudio.save(chunk_buffer, chunk, sample_rate, format='wav')
                chunks.append(chunk_buffer.getvalue())
            
            log_info(f"Audio split into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            log_error(f"Error preparing audio chunks: {str(e)}")
            raise

    async def _run_inference(
        self,
        audio_data: bytes,
        language: str,
        vocabulary: Optional[List[str]] = None
    ) -> Dict:
        """Run model inference."""
        try:
            import whisperx
            import io
            import numpy as np
            
            # Convert bytes to audio array
            audio_buffer = io.BytesIO(audio_data)
            audio = whisperx.load_audio(audio_buffer)
            
            # Unpack models
            whisper_model, diarize_model = self.model
            
            # Run ASR with Whisper
            result = whisper_model.transcribe(
                audio, 
                batch_size=self.batch_size,
                language=language
            )
            
            # Align whisper output
            align_model, metadata = whisperx.load_align_model(
                language_code=language,
                device=self.device
            )
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                device=self.device
            )
            
            # Run diarization
            diarize_segments = diarize_model(audio)
            
            # Assign speaker labels
            result = whisperx.assign_speakers(
                result["segments"],
                diarize_segments
            )
            
            # Apply vocabulary if provided
            if vocabulary and len(vocabulary) > 0:
                for segment in result["segments"]:
                    text = segment["text"]
                    for term in vocabulary:
                        # Simple case-insensitive replacement
                        # In a production system, this would use more sophisticated NLP
                        text = text.replace(term.lower(), term)
                        text = text.replace(term.upper(), term)
                        text = text.replace(term.capitalize(), term)
                    segment["text"] = text
            
            return result
        except Exception as e:
            log_error(f"Error running inference: {str(e)}")
            raise

    async def _combine_results(self, results: List[Dict]) -> Dict:
        """Combine chunk results."""
        try:
            # Initialize combined result
            combined_segments = []
            combined_text = ""
            
            # Track time offset for each chunk
            time_offset = 0.0
            
            for result in results:
                # Skip empty results
                if not result or "segments" not in result:
                    continue
                    
                # Process segments
                for segment in result.get("segments", []):
                    # Adjust timestamps
                    segment["start"] += time_offset
                    segment["end"] += time_offset
                    
                    # Add to combined segments
                    combined_segments.append(segment)
                    
                    # Add to combined text
                    if combined_text:
                        combined_text += " "
                    combined_text += segment.get("text", "")
                
                # Update time offset for next chunk
                if combined_segments:
                    time_offset = combined_segments[-1]["end"]
            
            # Format the final result
            return {
                "text": combined_text,
                "segments": combined_segments,
                "language": results[0].get("language") if results else None
            }
        except Exception as e:
            log_error(f"Error combining results: {str(e)}")
            raise

    async def _post_process(self, result: Dict) -> Dict:
        """Post-process transcription result."""
        try:
            # Format the result for the frontend
            processed_result = {
                "text": result.get("text", ""),
                "segments": [],
                "speakers": {},
                "language": result.get("language", "")
            }
            
            # Process segments
            speaker_map = {}
            for segment in result.get("segments", []):
                speaker = segment.get("speaker", "SPEAKER_UNKNOWN")
                
                # Track unique speakers
                if speaker not in speaker_map:
                    speaker_id = f"S{len(speaker_map) + 1}"
                    speaker_map[speaker] = speaker_id
                else:
                    speaker_id = speaker_map[speaker]
                
                # Add to processed segments
                processed_segment = {
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "text": segment.get("text", ""),
                    "speaker": speaker_id,
                    "confidence": segment.get("confidence", 0.0)
                }
                processed_result["segments"].append(processed_segment)
            
            # Add speaker information
            for original_id, speaker_id in speaker_map.items():
                processed_result["speakers"][speaker_id] = {
                    "id": speaker_id,
                    "name": f"Speaker {speaker_id.replace('S', '')}"
                }
            
            return processed_result
        except Exception as e:
            log_error(f"Error post-processing result: {str(e)}")
            raise
