import torch
import whisperx
import time
import logging
from pyannote.audio import Pipeline
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import ffmpeg
from pathlib import Path
import tempfile
import os
import asyncio
import zipfile

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio preprocessing using FFmpeg"""
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / "transcribo_audio"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def process_zip(
        self,
        zip_path: str,
        job_id: str
    ) -> Tuple[str, float]:
        """Process multiple audio files from ZIP archive"""
        try:
            # Create job-specific temp directory
            job_temp_dir = self.temp_dir / job_id
            job_temp_dir.mkdir(exist_ok=True)
            
            # Create directory for extracted files
            extract_dir = job_temp_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)
            
            # Extract ZIP
            logger.info(f"Extracting ZIP file for job {job_id}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Process each audio file
            audio_files = []
            total_duration = 0
            
            # Find all audio/video files
            for root, _, files in os.walk(extract_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        # Check if file is audio/video
                        probe = await self._probe_file(file_path)
                        if any(stream['codec_type'] == 'audio' for stream in probe['streams']):
                            # Process the audio file
                            processed_path, duration = await self.process_audio(file_path, f"{job_id}_{len(audio_files)}")
                            audio_files.append(processed_path)
                            total_duration += duration
                    except Exception as e:
                        logger.warning(f"Skipping file {file}: {str(e)}")
                        continue
            
            if not audio_files:
                raise Exception("No valid audio files found in ZIP")
            
            # Merge audio files if multiple found
            if len(audio_files) > 1:
                output_path = str(job_temp_dir / "merged_audio.mp4")
                await self._merge_audio_files(audio_files, output_path)
            else:
                output_path = audio_files[0]
            
            return output_path, total_duration
            
        except Exception as e:
            logger.error(f"Error processing ZIP file for job {job_id}: {str(e)}")
            self.cleanup(job_id)
            raise

    async def process_audio(
        self,
        input_path: str,
        job_id: str
    ) -> Tuple[str, float]:
        """Process audio file and return processed path and duration"""
        try:
            # Create job-specific temp directory
            job_temp_dir = self.temp_dir / job_id
            job_temp_dir.mkdir(exist_ok=True)
            output_path = str(job_temp_dir / "processed_audio.mp4")

            # Get file info
            probe = await self._probe_file(input_path)
            duration = float(probe['format']['duration'])

            # Audio filters
            audio_filters = [
                "lowpass=3000",  # Remove high frequencies
                "highpass=200",  # Remove low frequencies
                "loudnorm"       # Normalize audio levels
            ]

            # Check if input has video
            has_video = any(stream['codec_type'] == 'video' 
                          for stream in probe['streams'])

            # Build FFmpeg command
            if has_video:
                stream = ffmpeg.input(input_path)
                video = stream.video.filter('scale', -2, 320)
                audio = stream.audio.filter_multi_output(audio_filters)
                output = ffmpeg.output(
                    video, 
                    audio, 
                    output_path,
                    acodec='aac',
                    vcodec='libx264',
                    strict='-2'
                )
            else:
                stream = ffmpeg.input(input_path)
                audio = stream.audio.filter_multi_output(audio_filters)
                output = ffmpeg.output(
                    audio,
                    output_path,
                    acodec='aac',
                    strict='-2'
                )

            # Run FFmpeg
            logger.info(f"Processing audio for job {job_id}")
            await self._run_ffmpeg(output)
            
            return output_path, duration

        except Exception as e:
            logger.error(f"Error processing audio for job {job_id}: {str(e)}")
            if os.path.exists(output_path):
                os.remove(output_path)
            raise

    async def _probe_file(self, file_path: str) -> dict:
        """Get file information using FFprobe"""
        try:
            probe = await asyncio.to_thread(
                ffmpeg.probe,
                file_path
            )
            return probe
        except ffmpeg.Error as e:
            logger.error(f"FFprobe error: {e.stderr.decode()}")
            raise

    async def _run_ffmpeg(self, stream) -> None:
        """Run FFmpeg command asynchronously"""
        try:
            await asyncio.to_thread(
                stream.run,
                capture_stdout=True,
                capture_stderr=True
            )
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error: {e.stderr.decode()}")
            raise

    async def _merge_audio_files(self, audio_files: List[str], output_path: str):
        """Merge multiple audio files into one"""
        try:
            # Create filter complex for mixing audio
            inputs = []
            for file in audio_files:
                inputs.append(ffmpeg.input(file))
            
            # Mix all audio streams
            audio = ffmpeg.filter(
                [input.audio for input in inputs],
                'amix',
                inputs=len(inputs),
                normalize=0
            )
            
            # Output mixed audio
            output = ffmpeg.output(
                audio,
                output_path,
                acodec='aac',
                strict='-2'
            )
            
            await self._run_ffmpeg(output)
            logger.info(f"Successfully merged {len(audio_files)} audio files")
            
        except Exception as e:
            logger.error(f"Error merging audio files: {str(e)}")
            raise

    def cleanup(self, job_id: str) -> None:
        """Clean up temporary files"""
        try:
            job_temp_dir = self.temp_dir / job_id
            if job_temp_dir.exists():
                for file in job_temp_dir.glob("*"):
                    file.unlink()
                job_temp_dir.rmdir()
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {str(e)}")
    

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
        self.audio_processor = AudioProcessor()
        self._init_models()
        
        # Language settings
        self.primary_languages = {'de', 'en', 'gsw'}  # German, English, Swiss German
        self.language_names = {
            'de': 'German',
            'en': 'English',
            'gsw': 'Swiss German',
            'fr': 'French',
            'it': 'Italian',
            'rm': 'Romansh'
        }

    def _init_models(self):
        """Initialize whisper and diarization models"""
        whisper_device = "cpu" if self.device == "mps" else self.device
        compute_type = "float32" if whisper_device == "cpu" else self.compute_type

        # Load whisper model
        whisper_model = "tiny.en" if self.device == "mps" else "large-v3"
        self.model = whisperx.load_model(
            whisper_model,
            whisper_device,
            compute_type=compute_type
        )
        
        # Load diarization model
        self.diarize_model = Pipeline.from_pretrained(
            "pyannote/speaker-diarization",
            use_auth_token=self.hf_token
        ).to(torch.device(self.device))

    def prepare_vocabulary(self, vocabulary: List[str]) -> str:
        """
        Prepare vocabulary for the transcription model.
        Returns formatted string of vocabulary words.
        """
        if not vocabulary:
            return ""
        
        # Clean and format vocabulary words
        cleaned_words = [word.strip() for word in vocabulary if word.strip()]
        return " ".join(cleaned_words)

    def format_timestamp(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60
        milliseconds = int((seconds % 1) * 1000)
        seconds = int(seconds)
        
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def create_srt(self, segments: List[Dict]) -> str:
        """Generate SRT format subtitles from transcription segments"""
        srt_content = []
        for i, segment in enumerate(segments, 1):
            start_time = self.format_timestamp(segment['start'])
            end_time = self.format_timestamp(segment['end'])
            
            # Format speaker label if available
            speaker_label = f"[{segment.get('speaker', 'Unknown')}] "
            
            # Add language tag for foreign segments
            if segment.get('is_foreign', False):
                speaker_label += f"[{segment.get('language_name', 'Unknown')}] "
            
            srt_content.extend([
                str(i),
                f"{start_time} --> {end_time}",
                f"{speaker_label}{segment['text'].strip()}",
                ""  # Empty line between entries
            ])
        
        return "\n".join(srt_content)

    async def detect_segment_language(
        self,
        segment_audio: torch.Tensor
    ) -> Dict[str, any]:
        """Detect language for a single segment"""
        try:
            # Get model features
            segment = whisperx.audio.log_mel_spectrogram(
                segment_audio,
                n_mels=self.model.model.feat_kwargs.get("feature_size", 80)
            )
            
            # Get encoder output
            encoder_output = self.model.model.encode(segment)
            
            # Detect language
            results = self.model.model.detect_language(encoder_output)
            language_token, confidence = results[0][0]
            
            # Extract language code
            language_code = language_token[2:-2]  # Remove <> tokens
            
            return {
                'language': language_code,
                'language_name': self.language_names.get(language_code, language_code),
                'language_confidence': confidence,
                'is_foreign': language_code not in self.primary_languages
            }
            
        except Exception as e:
            logger.error(f"Language detection error: {str(e)}")
            return {
                'language': 'de',
                'language_name': 'German',
                'language_confidence': 0.5,
                'is_foreign': False
            }

async def transcribe(
    self,
    audio_path: str,
    job_id: str = None,
    vocabulary: Optional[List[str]] = None
) -> dict:
    """
    Transcribe audio file with diarization and custom vocabulary
    """
    try:
        start_time = time.time()
        logger.info(f"Starting transcription for job {job_id}")

        # Check if file is ZIP
        if zipfile.is_zipfile(audio_path):
            logger.info("Processing ZIP file...")
            processed_path, duration = await self.audio_processor.process_zip(
                audio_path,
                job_id
            )
        else:
            # Regular audio processing
            processed_path, duration = await self.audio_processor.process_audio(
                audio_path,
                job_id
            )

        # Load processed audio
        audio = whisperx.load_audio(processed_path)

        # Prepare vocabulary if provided
        prompt = self.prepare_vocabulary(vocabulary)
        
        # Set prompt if vocabulary exists
        if prompt:
            self.model.options = self.model.options._replace(prefix=prompt)

        # Transcribe with whisper
        logger.info("Running initial transcription...")
        result = self.model.transcribe(
            audio,
            batch_size=self.batch_size,
            language="de"
        )

        # Reset prompt after transcription
        if prompt:
            self.model.options = self.model.options._replace(prefix=None)

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

        # Detect languages for each segment
        logger.info("Detecting segment languages...")
        for segment in result["segments"]:
            start_idx = int(segment['start'] * 16000)
            end_idx = int(segment['end'] * 16000)
            segment_audio = audio[start_idx:end_idx]
            
            # Add padding if segment is too short
            if len(segment_audio) < 16000:
                segment_audio = torch.nn.functional.pad(
                    segment_audio,
                    (0, 16000 - len(segment_audio))
                )
            
            # Detect language
            lang_info = await self.detect_segment_language(segment_audio)
            segment.update(lang_info)

        # Generate SRT content
        srt_content = self.create_srt(result["segments"])

        duration = time.time() - start_time
        logger.info(f"Transcription completed in {duration:.2f} seconds")

        # Cleanup
        self.audio_processor.cleanup(job_id)

        return {
            "segments": result["segments"],
            "language": result["language"],
            "duration": duration,
            "srt_content": srt_content,
            "completed_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Transcription failed: {str(e)}")
        # Ensure cleanup on error
        self.audio_processor.cleanup(job_id)
        raise