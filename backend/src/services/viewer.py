import os
import logging
from typing import Optional, Dict, List
from pathlib import Path
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from ..models.job import Transcription, Speaker, Segment
from .storage import StorageService

logger = logging.getLogger(__name__)

class ViewerService:
    def __init__(self):
        """Initialize viewer service"""
        # Get configuration
        self.template_dir = Path(os.getenv("TEMPLATE_DIR", "templates"))
        self.asset_dir = Path(os.getenv("ASSET_DIR", "assets"))
        
        # Initialize Jinja environment
        self.env = Environment(
            loader=FileSystemLoader(self.template_dir),
            autoescape=True
        )
        
        # Load templates
        self.editor_template = self.env.get_template("editor.html")
        self.viewer_template = self.env.get_template("viewer.html")
        
        # Initialize storage
        self.storage = StorageService()
        
        logger.info("Viewer service initialized")

    async def create_editor(
        self,
        user_id: str,
        job_id: str,
        transcription: Transcription,
        audio_url: str
    ) -> str:
        """Create editor HTML"""
        try:
            # Load editor assets
            css = await self._load_asset("editor.css")
            js = await self._load_asset("editor.js")
            
            # Render template
            html = self.editor_template.render(
                user_id=user_id,
                job_id=job_id,
                transcription=transcription,
                audio_url=audio_url,
                css=css,
                js=js,
                timestamp=datetime.utcnow().isoformat()
            )
            
            return html
            
        except Exception as e:
            logger.error(f"Failed to create editor: {str(e)}")
            raise

    async def create_viewer(
        self,
        user_id: str,
        job_id: str,
        transcription: Transcription,
        audio_url: str,
        options: Optional[Dict] = None
    ) -> str:
        """Create viewer HTML"""
        try:
            # Set default options
            if not options:
                options = {
                    "combine_speakers": True,
                    "show_timestamps": True,
                    "include_foreign": True,
                    "max_segment_length": 500
                }
            
            # Process transcription
            segments = await self._process_segments(
                transcription.segments,
                options
            )
            
            # Load viewer assets
            css = await self._load_asset("viewer.css")
            js = await self._load_asset("viewer.js")
            
            # Render template
            html = self.viewer_template.render(
                user_id=user_id,
                job_id=job_id,
                segments=segments,
                speakers=transcription.speakers,
                audio_url=audio_url,
                options=options,
                css=css,
                js=js,
                timestamp=datetime.utcnow().isoformat()
            )
            
            return html
            
        except Exception as e:
            logger.error(f"Failed to create viewer: {str(e)}")
            raise

    async def save_editor_state(
        self,
        user_id: str,
        job_id: str,
        state: Dict
    ):
        """Save editor state"""
        try:
            # Store state
            await self.storage.store_file(
                user_id,
                json.dumps(state).encode(),
                f"{job_id}_editor.json",
                "temp"
            )
            
            logger.info(f"Saved editor state for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to save editor state: {str(e)}")
            raise

    async def load_editor_state(
        self,
        user_id: str,
        job_id: str
    ) -> Optional[Dict]:
        """Load editor state"""
        try:
            # Get state file
            data = await self.storage.retrieve_file(
                user_id,
                f"{job_id}_editor.json",
                "temp"
            )
            
            return json.loads(data) if data else None
            
        except Exception as e:
            logger.error(f"Failed to load editor state: {str(e)}")
            return None

    async def export_text(
        self,
        transcription: Transcription,
        options: Optional[Dict] = None
    ) -> str:
        """Export transcription as text"""
        try:
            # Set default options
            if not options:
                options = {
                    "combine_speakers": True,
                    "show_timestamps": True,
                    "include_foreign": True,
                    "max_segment_length": 500
                }
            
            # Process segments
            segments = await self._process_segments(
                transcription.segments,
                options
            )
            
            # Build text
            text = []
            current_speaker = None
            
            for segment in segments:
                # Add speaker header
                if segment["speaker"] != current_speaker:
                    current_speaker = segment["speaker"]
                    if options["show_timestamps"]:
                        text.append(f"\n{current_speaker} ({segment['timestamp']}):")
                    else:
                        text.append(f"\n{current_speaker}:")
                
                # Add text
                text.append(segment["text"])
            
            return "\n".join(text)
            
        except Exception as e:
            logger.error(f"Failed to export text: {str(e)}")
            raise

    async def export_srt(
        self,
        transcription: Transcription,
        options: Optional[Dict] = None
    ) -> str:
        """Export transcription as SRT"""
        try:
            # Set default options
            if not options:
                options = {
                    "combine_speakers": False,
                    "include_foreign": True,
                    "max_line_length": 42
                }
            
            # Process segments
            segments = await self._process_segments(
                transcription.segments,
                options
            )
            
            # Build SRT
            srt = []
            for i, segment in enumerate(segments, 1):
                # Add index
                srt.append(str(i))
                
                # Add timecode
                start = self._format_timecode(segment["start"])
                end = self._format_timecode(segment["end"])
                srt.append(f"{start} --> {end}")
                
                # Add text
                if options["combine_speakers"]:
                    text = segment["text"]
                else:
                    text = f"{segment['speaker']}: {segment['text']}"
                
                # Split long lines
                if options["max_line_length"]:
                    text = self._split_lines(text, options["max_line_length"])
                
                srt.append(text)
                srt.append("")
            
            return "\n".join(srt)
            
        except Exception as e:
            logger.error(f"Failed to export SRT: {str(e)}")
            raise

    async def _process_segments(
        self,
        segments: List[Segment],
        options: Dict
    ) -> List[Dict]:
        """Process segments according to options"""
        try:
            processed = []
            current_speaker = None
            current_text = []
            current_start = None
            
            for segment in segments:
                # Skip foreign segments if disabled
                if not options["include_foreign"]:
                    if segment.language not in ["de", "en"]:
                        continue
                
                # Combine segments from same speaker
                if options["combine_speakers"]:
                    if segment.speaker_idx == current_speaker:
                        current_text.append(segment.text)
                        continue
                    elif current_text:
                        processed.append({
                            "speaker": f"Speaker {current_speaker + 1}",
                            "text": " ".join(current_text),
                            "timestamp": self._format_timestamp(current_start),
                            "start": current_start,
                            "end": segment.start
                        })
                
                # Start new segment
                current_speaker = segment.speaker_idx
                current_text = [segment.text]
                current_start = segment.start
                
                if not options["combine_speakers"]:
                    processed.append({
                        "speaker": f"Speaker {segment.speaker_idx + 1}",
                        "text": segment.text,
                        "timestamp": self._format_timestamp(segment.start),
                        "start": segment.start,
                        "end": segment.end
                    })
            
            # Add final combined segment
            if options["combine_speakers"] and current_text:
                processed.append({
                    "speaker": f"Speaker {current_speaker + 1}",
                    "text": " ".join(current_text),
                    "timestamp": self._format_timestamp(current_start),
                    "start": current_start,
                    "end": segments[-1].end
                })
            
            return processed
            
        except Exception as e:
            logger.error(f"Failed to process segments: {str(e)}")
            raise

    async def _load_asset(self, filename: str) -> str:
        """Load asset file"""
        try:
            path = self.asset_dir / filename
            with open(path) as f:
                return f.read()
                
        except Exception as e:
            logger.error(f"Failed to load asset {filename}: {str(e)}")
            raise

    def _format_timestamp(self, seconds: float) -> str:
        """Format timestamp as HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _format_timecode(self, seconds: float) -> str:
        """Format timecode as HH:MM:SS,mmm"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    def _split_lines(self, text: str, max_length: int) -> str:
        """Split text into lines of maximum length"""
        if len(text) <= max_length:
            return text
            
        words = text.split()
        lines = []
        current_line = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # Add space
            if current_length + word_length > max_length:
                lines.append(" ".join(current_line))
                current_line = [word]
                current_length = word_length
            else:
                current_line.append(word)
                current_length += word_length
        
        if current_line:
            lines.append(" ".join(current_line))
        
        return "\n".join(lines)
