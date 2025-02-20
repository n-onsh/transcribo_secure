# transcriber/src/services/transcription.py
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
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import numpy as np
from ..utils.metrics import (
    TRANSCRIPTION_DURATION,
    TRANSCRIPTION_TOTAL,
    AUDIO_DURATION,
    track_time,
)

logger = logging.getLogger(__name__)

class AudioProcessor:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "transcribo_secure"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

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

    async def _merge_audio_files(self, audio_files: List[str], output_path: str):
        inputs = [ffmpeg.input(f) for f in audio_files]
        audio = ffmpeg.filter([i.audio for i in inputs], 'amix', inputs=len(inputs))
        output = ffmpeg.output(audio, output_path, acodec='aac')
        await self._run_ffmpeg(output)

    def cleanup(self, job_id: str):
        job_dir = self.temp_dir / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir)

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

    def initialize_models(self):
        try:
            logger.info("Loading Whisper model...")
            self.model = whisperx.load_model("large-v3", self.device, compute_type="float16")
            
            logger.info("Loading diarization model...")
            self.diarize_model = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                use_auth_token=self.hf_token
            )
            self.diarize_model.to(torch.device(self.device))
        except Exception as e:
            logger.error(f"Model initialization failed: {e}")
            raise

    @track_time(TRANSCRIPTION_DURATION)
    async def transcribe(self, audio_path: str, job_id: str, vocabulary: Optional[List[str]] = None) -> Dict:
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
            result = self.model.transcribe(
                audio, 
                batch_size=self.batch_size,
                language="de",
                initial_prompt=" ".join(vocabulary or [])
            )

            # Align transcription
            model_a, metadata = whisperx.load_align_model(
                language_code=result["language"],
                device=self.device
            )
            result = whisperx.align(
                result["segments"],
                model_a,
                metadata,
                audio,
                self.device,
                return_char_alignments=False
            )

            # Run diarization
            diarize_segments = self.diarize_model({"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": 16000})
            diarize_df = whisperx.diarize.segments_to_df(diarize_segments)
            result = whisperx.assign_word_speakers(diarize_df, result)

            # Detect languages for segments
            for segment in result["segments"]:
                start_sample = int(segment["start"] * 16000)
                end_sample = int(segment["end"] * 16000)
                segment_audio = audio[start_sample:end_sample]
                
                if len(segment_audio) > 0:
                    segment_mel = whisperx.audio.log_mel_spectrogram(segment_audio)
                    segment_mel = segment_mel.to(self.device)
                    
                    with torch.no_grad():
                        encoder_output = self.model.model.encoder(segment_mel.unsqueeze(0))
                        probs = self.model.model.decoder.detect_language(encoder_output)
                        language_code = max(probs.items(), key=lambda x: x[1])[0]
                        segment["language"] = language_code
                        segment["is_foreign"] = language_code not in self.primary_languages

            TRANSCRIPTION_TOTAL.labels(status="success").inc()
            process_time = time.time() - start_time

            return {
                "segments": result["segments"],
                "language": result["language"],
                "duration": process_time,
                "completed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            TRANSCRIPTION_TOTAL.labels(status="failure").inc()
            logger.error(f"Transcription failed: {e}")
            raise
        finally:
            self.audio_processor.cleanup(job_id)

    @property
    def is_ready(self) -> bool:
        return self.model is not None and self.diarize_model is not None