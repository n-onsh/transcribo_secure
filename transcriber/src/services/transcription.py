import torch
import whisperx
import time
import logging
import types
from pyannote.audio import Pipeline
from typing import Optional

logger = logging.getLogger(__name__)

class TranscriptionService:
    def __init__(
        self,
        device: str = "cuda",
        batch_size: int = 32,
        hf_token: Optional[str] = None,
        compute_type: str = "float16"
    ):
        self.device = device
        self.batch_size = batch_size
        self.hf_token = hf_token
        self.compute_type = compute_type
        
        # Initialize models
        logger.info("Initializing models...")
        self._init_models()
        logger.info("Models initialized successfully")

    def _init_models(self):
        """Initialize whisper and diarization models"""
        whisper_device = "cpu" if self.device == "mps" else self.device
        if whisper_device == "cpu":
            compute_type = "float32"
        else:
            compute_type = self.compute_type

        # Load whisper model
        whisper_model = "tiny.en" if self.device == "mps" else "large-v3"
        self.model = whisperx.load_model(
            whisper_model,
            whisper_device,
            compute_type=compute_type
        )

        # Override get_prompt method
        self.model.model.get_prompt = types.MethodType(self._get_prompt, self.model.model)

        # Load diarization model
        self.diarize_model = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token=self.hf_token
        ).to(torch.device(self.device))

    def _get_prompt(self, model, tokenizer, previous_tokens, without_timestamps, prefix):
        """Custom prompt method for Whisper model"""
        prompt = []

        if previous_tokens or prefix:
            prompt.append(tokenizer.sot_prev)
            if prefix:
                hotwords_tokens = tokenizer.encode(" " + prefix.strip())
                if len(hotwords_tokens) >= model.max_length // 2:
                    hotwords_tokens = hotwords_tokens[: model.max_length // 2 - 1]
                prompt.extend(hotwords_tokens)
            if prefix and previous_tokens:
                prompt.extend(previous_tokens[-(model.max_length // 2 - 1):])

        prompt.extend(tokenizer.sot_sequence)

        if without_timestamps:
            prompt.append(tokenizer.no_timestamps)

        return prompt

    async def transcribe(self, audio_path: str, job_id: str = None) -> dict:
        """
        Transcribe audio file with diarization
        Returns: Dictionary containing transcription segments with speaker labels
        """
        try:
            start_time = time.time()
            logger.info(f"Starting transcription for job {job_id}")

            # Load audio
            audio = whisperx.load_audio(audio_path)

            # Transcribe with whisper
            logger.info("Running initial transcription...")
            result = self.model.transcribe(
                audio,
                batch_size=self.batch_size,
                language="de"
            )

            # Align whisper output
            logger.info("Aligning transcription...")
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

            # Diarize
            logger.info("Running speaker diarization...")
            diarize_segments = self.diarize_model(
                {"waveform": torch.from_numpy(audio).unsqueeze(0), "sample_rate": 16000}
            )

            # Convert diarization results to dataframe
            diarize_df = whisperx.diarize.segments_to_df(diarize_segments)
            
            # Assign speakers to words
            logger.info("Assigning speakers to segments...")
            result = whisperx.assign_word_speakers(diarize_df, result)

            duration = time.time() - start_time
            logger.info(f"Transcription completed in {duration:.2f} seconds")

            return {
                "segments": result["segments"],
                "language": result["language"],
                "duration": duration
            }

        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            raise