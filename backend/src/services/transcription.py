import os
import io
import logging
import torch
import whisperx
import numpy as np
from typing import Optional, Callable, Dict, List
from pyannote.audio import Pipeline
from pydub import AudioSegment
import ffmpeg
from ..models.job import Transcription, Speaker, Segment
import uuid

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(self):
        """Initialize transcription service"""
        # Get configuration
        self.device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
        self.batch_size = int(os.getenv("BATCH_SIZE", "4"))
        self.compute_type = "float16" if self.device == "cuda" else "float32"
        self.hf_token = os.getenv("HF_AUTH_TOKEN")
        self.max_file_size = int(os.getenv("MAX_AUDIO_SIZE_MB", "500")) * 1024 * 1024
        self.model_cache_size = int(os.getenv("MODEL_CACHE_SIZE", "3"))
        self.supported_languages = {
            "de": "German",
            "en": "English",
            "fr": "French",
            "it": "Italian"
        }
        
        if not self.hf_token:
            raise ValueError("HF_AUTH_TOKEN environment variable not set")
        
        # Initialize models with LRU cache
        self.model_cache = {}
        self.model_usage = {}
        self.whisper_model = None
        self.diarize_model = None
        
        logger.info(f"Transcription service initialized (device: {self.device})")

    def _cleanup_model_cache(self):
        """Remove least recently used models if cache is full"""
        try:
            while len(self.model_cache) > self.model_cache_size:
                # Find least recently used model
                lru_model = min(self.model_usage.items(), key=lambda x: x[1])[0]
                
                # Remove from cache
                del self.model_cache[lru_model]
                del self.model_usage[lru_model]
                
                # Force garbage collection
                torch.cuda.empty_cache() if torch.cuda.is_available() else None
                
                logger.info(f"Removed model {lru_model} from cache")
                
        except Exception as e:
            logger.error(f"Failed to cleanup model cache: {str(e)}")

    async def _load_models(self, language: str = "de"):
        """Load models if not already loaded"""
        try:
            # Validate language
            if language not in self.supported_languages:
                raise ValueError(f"Unsupported language: {language}")
            
            # Update Whisper model if language changed
            model_key = f"whisper_{language}"
            if model_key not in self.model_cache:
                # Cleanup cache if needed
                self._cleanup_model_cache()
                
                # Load new model
                self.model_cache[model_key] = whisperx.load_model(
                    "large-v3",
                    self.device,
                    compute_type=self.compute_type,
                    language=language
                )
                logger.info(f"Loaded Whisper model for {language}")
            
            # Update usage timestamp
            self.model_usage[model_key] = datetime.utcnow()
            self.whisper_model = self.model_cache[model_key]
            
            # Load diarization model if needed
            if not self.diarize_model:
                self.diarize_model = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.0",
                    use_auth_token=self.hf_token
                ).to(torch.device(self.device))
                logger.info("Loaded diarization model")
                
        except Exception as e:
            logger.error(f"Failed to load models: {str(e)}")
            raise

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Transcription:
        """Transcribe audio data"""
        try:
            # Validate file size
            if len(audio_data) > self.max_file_size:
                raise ValueError(f"Audio file too large (max {self.max_file_size/1024/1024:.1f}MB)")
            
            # Detect or validate language
            if language:
                if language not in self.supported_languages:
                    raise ValueError(f"Unsupported language: {language}")
            else:
                # Convert audio for language detection
                audio = await self._load_audio(audio_data)
                language = self._detect_language(audio)
            
            # Load models for detected/specified language
            await self._load_models(language)
            
            # Convert audio to WAV
            audio = await self._load_audio(audio_data)
            
            # Report progress
            if progress_callback:
                await progress_callback(10.0)
            
            # Get audio duration
            duration = len(audio) / 16000  # whisperx uses 16kHz
            
            # Transcribe with Whisper
            logger.info("Starting transcription")
            result = self.whisper_model.transcribe(
                audio,
                batch_size=self.batch_size
            )
            
            # Report progress
            if progress_callback:
                await progress_callback(40.0)
            
            # Align transcription
            logger.info("Aligning transcription")
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
            
            # Report progress
            if progress_callback:
                await progress_callback(60.0)
            
            # Perform speaker diarization
            logger.info("Performing speaker diarization")
            diarize_segments = await self._diarize_audio(audio)
            
            # Report progress
            if progress_callback:
                await progress_callback(80.0)
            
            # Assign speakers to segments
            logger.info("Assigning speakers")
            segments = []
            speakers = {}
            
            for segment in result["segments"]:
                # Find overlapping diarization segment
                speaker_id = None
                max_overlap = 0
                
                for d_segment in diarize_segments:
                    overlap_start = max(segment["start"], d_segment["start"])
                    overlap_end = min(segment["end"], d_segment["end"])
                    overlap = max(0, overlap_end - overlap_start)
                    
                    if overlap > max_overlap:
                        max_overlap = overlap
                        speaker_id = d_segment["speaker"]
                
                # Get or create speaker index
                if speaker_id not in speakers:
                    speaker_idx = len(speakers)
                    speakers[speaker_id] = Speaker(
                        name=f"Speaker {speaker_idx + 1}"
                    )
                
                # Create segment
                segments.append(Segment(
                    id=str(uuid.uuid4()),
                    start=segment["start"],
                    end=segment["end"],
                    text=segment["text"].strip(),
                    speaker_idx=list(speakers.keys()).index(speaker_id),
                    words=segment.get("words", [])
                ))
            
            # Create transcription
            transcription = Transcription(
                speakers=list(speakers.values()),
                segments=segments,
                language=result["language"],
                duration=duration,
                word_count=sum(len(s["words"]) for s in result["segments"])
            )
            
            # Report completion
            if progress_callback:
                await progress_callback(100.0)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise

    async def _load_audio(self, audio_data: bytes) -> np.ndarray:
        """Load and normalize audio data"""
        try:
            # Convert to WAV using ffmpeg
            audio = (
                ffmpeg.input("pipe:0")
                .output(
                    "pipe:1",
                    acodec="pcm_s16le",
                    ac=1,
                    ar="16k",
                    loglevel="error"
                )
                .run(input=audio_data, capture_stdout=True)[0]
            )
            
            # Convert to numpy array
            audio = np.frombuffer(audio, np.int16).flatten().astype(np.float32) / 32768.0
            
            return audio
            
        except Exception as e:
            logger.error(f"Failed to load audio: {str(e)}")
            raise

    async def _diarize_audio(self, audio: np.ndarray) -> List[Dict]:
        """Perform speaker diarization"""
        try:
            # Create waveform tensor
            waveform = torch.from_numpy(audio).unsqueeze(0)
            
            # Run diarization
            diarization = self.diarize_model({
                "waveform": waveform,
                "sample_rate": 16000
            })
            
            # Convert to segments
            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append({
                    "start": turn.start,
                    "end": turn.end,
                    "speaker": speaker
                })
            
            return segments
            
        except Exception as e:
            logger.error(f"Diarization failed: {str(e)}")
            raise

    def _detect_language(self, audio: np.ndarray) -> str:
        """Detect audio language"""
        try:
            # Use Whisper's language detection
            audio_features = self.whisper_model.feature_extractor(audio)
            result = self.whisper_model.detect_language(audio_features)
            return result[0][0]
            
        except Exception as e:
            logger.error(f"Language detection failed: {str(e)}")
            raise
