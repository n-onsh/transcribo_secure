"""Transcription service."""

import gc
import os
import io
import asyncio
import logging
import torch
import torchaudio
from typing import Dict, Optional, List, BinaryIO
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

    async def validate_audio(self, audio_file: BinaryIO) -> Dict:
        """Validate an audio file."""
        try:
            # Read file into memory buffer
            buffer = io.BytesIO(audio_file.read())
            audio_file.seek(0)
            
            # Load audio metadata
            info = torchaudio.info(buffer)
            
            # Validate format and properties
            errors = []
            
            if info.sample_rate < 8000:
                errors.append("Sample rate too low (minimum 8kHz)")
            
            if info.num_frames / info.sample_rate > 7200:  # 2 hours
                errors.append("Audio too long (maximum 2 hours)")
            
            if info.num_frames == 0:
                errors.append("Empty audio file")
            
            result = {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'metadata': {
                    'sample_rate': info.sample_rate,
                    'num_channels': info.num_channels,
                    'duration': info.num_frames / info.sample_rate
                }
            }
            
            if result['is_valid']:
                log_info("Audio file validation passed")
            else:
                log_warning("Audio file validation failed", extra=result)
            
            return result

        except Exception as e:
            log_error(f"Error validating audio file: {str(e)}")
            raise

    async def get_languages(self) -> List[Dict]:
        """Get supported languages."""
        try:
            languages = [
                {'code': 'de', 'name': 'German'},
                {'code': 'en', 'name': 'English'},
                {'code': 'fr', 'name': 'French'},
                {'code': 'it', 'name': 'Italian'}
            ]
            log_info(f"Listed {len(languages)} supported languages")
            return languages

        except Exception as e:
            log_error(f"Error getting supported languages: {str(e)}")
            raise

    async def _load_model(self):
        """Load the transcription model."""
        try:
            # Implementation would load model
            # For example:
            # model = whisper.load_model(self.model_path)
            # model.to(self.device)
            # return model
            return None
        except Exception as e:
            log_error(f"Error loading model: {str(e)}")
            raise

    async def _unload_model(self):
        """Unload the transcription model."""
        try:
            if self.model:
                # Implementation would unload model
                # For example:
                # del self.model
                # torch.cuda.empty_cache()
                pass
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
            
            # Calculate chunk size in samples
            chunk_samples = self.chunk_size * sample_rate
            
            # Split into chunks
            chunks = []
            for i in range(0, waveform.size(1), chunk_samples):
                chunk = waveform[:, i:i + chunk_samples]
                chunk_buffer = io.BytesIO()
                torchaudio.save(chunk_buffer, chunk, sample_rate, format='wav')
                chunks.append(chunk_buffer.getvalue())
            
            return chunks

        except Exception as e:
            log_error(f"Error preparing audio chunks: {str(e)}")
            raise

    async def _run_inference(
        self,
        audio_data: bytes,
        language: str,
        vocabulary: Optional[List[str]]
    ) -> Dict:
        """Run model inference."""
        try:
            # Implementation would run inference
            # For example:
            # audio = whisper.load_audio(audio_data)
            # result = self.model.transcribe(audio, language=language)
            # return result
            return {}
        except Exception as e:
            log_error(f"Error running inference: {str(e)}")
            raise

    async def _combine_results(self, results: List[Dict]) -> Dict:
        """Combine chunk results."""
        try:
            # Implementation would combine results
            # For example:
            # combined_text = ' '.join(r['text'] for r in results)
            # combined_segments = []
            # offset = 0
            # for r in results:
            #     for s in r['segments']:
            #         s['start'] += offset
            #         s['end'] += offset
            #         combined_segments.append(s)
            #     offset = combined_segments[-1]['end']
            # return {'text': combined_text, 'segments': combined_segments}
            return {}
        except Exception as e:
            log_error(f"Error combining results: {str(e)}")
            raise

    async def _post_process(self, result: Dict) -> Dict:
        """Post-process transcription result."""
        try:
            # Implementation would post-process
            # For example:
            # - Clean up text
            # - Normalize timestamps
            # - Apply vocabulary
            return result
        except Exception as e:
            log_error(f"Error post-processing result: {str(e)}")
            raise
