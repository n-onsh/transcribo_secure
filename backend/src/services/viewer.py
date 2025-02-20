import logging
from typing import List, Dict, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

class ViewerService:
    def __init__(self, base_template_path: Optional[str] = None):
        self.base_template_path = base_template_path or Path(__file__).parent / "templates" / "editor.html"
        
    def create_viewer(
        self,
        segments: List[Dict],
        media_url: str,
        combine_speaker: bool = True,
        encode_base64: bool = False
    ) -> str:
        """Generate viewer HTML from transcription segments"""
        try:
            content = []
            content.append(self._generate_header())
            content.append(self._generate_navbar())
            content.append(self._generate_video_player(media_url, encode_base64))
            content.append(self._generate_buttons())
            content.append(self._generate_metadata())
            content.append(self._generate_speaker_info(segments))
            content.append(self._generate_transcript(segments, combine_speaker))
            content.append(self._generate_javascript(segments, media_url, encode_base64))
            
            return "\n".join(content)
            
        except Exception as e:
            logger.error(f"Error creating viewer: {str(e)}")
            raise

    def _generate_header(self) -> str:
        """Generate HTML header with styles"""
        return """
<!doctype html>
<html lang="en">
<meta http-equiv='Content-Type' content='text/html;charset=UTF-8'>
<head>
    <style>
        @charset "UTF-8";
        .sticky-offset { top: 130px; }
        .segment { padding-right: 8px; }
        *[contenteditable]:empty:before { content: "\\feff-"; }
        /* Bootstrap styles would go here */
    </style>
</head>
"""

    def _generate_navbar(self) -> str:
        """Generate navigation bar"""
        return """
<body>
    <nav class="navbar sticky-top navbar-light" style="background-color: #0070b4; z-index: 999">
        <div class="container">
            <span class="navbar-brand">TranscriboZH</span>
        </div>
    </nav>
"""

    def _generate_video_player(self, media_url: str, encode_base64: bool) -> str:
        """Generate video player section"""
        return f"""
    <div class="row container justify-content-center align-items-start" style="max-width: 200ch; margin-left: auto; margin-right: auto; margin-bottom: 0px;">
        <div class="col-md-6 sticky-top sticky-offset" style="width: 40%; z-index: 1; margin-bottom: 0px;">
            <div style="padding: 0">
                <video id="player" width="100%" style="max-height: 250px" src="{media_url}" type="video/MP4" controls="controls" position="sticky"></video>
"""

    def _generate_buttons(self) -> str:
        """Generate editor buttons"""
        return """
            <div style="margin-top:10px;" class="viewer-hidden">
                <a href="#" id="viewer-link" onclick="viewerClick()" class="btn btn-primary">Create Viewer</a>
                <a href="#" id="text-link" onclick="textClick()" class="btn btn-primary">Export Text</a>
                <a href="#" id="download-link" onclick="downloadClick()" class="btn btn-primary">Save</a>
                <br>
                <span>Delay: </span><span contenteditable="true" id="delay" class="border rounded"></span>
                <input type="checkbox" id="ignore_lang" value="ignore_lang" style="margin-left: 5px" onclick="changeCheckbox(this)"/>
                <label for="ignore_lang">Remove foreign languages on export</label>
            </div>
"""

    def _generate_metadata(self) -> str:
        """Generate metadata section"""
        return f"""
            <div style="margin-top:10px;">
                <label for="nr">Hash</label><span id="hash" class="form-control">0</span>
                <label for="date">Transcription Date</label><span contenteditable="true" class="form-control">{datetime.now().strftime('%d-%m-%Y')}</span>
            </div>
"""

    def _generate_speaker_info(self, segments: List[Dict]) -> str:
        """Generate speaker information section"""
        speakers = sorted(set(seg["speaker"] for seg in segments if seg.get("speaker")))
        content = []
        content.append('<div style="margin-top:10px;" class="viewer-hidden">')
        
        for idx, speaker in enumerate(speakers):
            content.append(f"""
                <span contenteditable="true" class="form-control" id="IN_SPEAKER_{str(idx).zfill(2)}" style="margin-top:4px;">Person {speaker[-2:]}</span>
            """)
        
        content.append('<br><br><br><br><br></div>')
        return "\n".join(content)

    def _generate_transcript(self, segments: List[Dict], combine_speaker: bool) -> str:
        """Generate transcript section"""
        content = []
        content.append('<div class="col-md-6" style="width: 60%; max-width: 90ch; z-index: 1; margin-left: auto; margin-right: auto">')
        content.append('<div class="wrapper" style="margin: 0.5rem auto 0; max-width: 80ch;" id="editor">')

        last_speaker = None
        for i, segment in enumerate(segments):
            if not combine_speaker or last_speaker != segment.get("speaker"):
                if last_speaker is not None:
                    content.append("</p></div>")
                content.append('<div>')
                content.append(self._generate_segment_header(segment, i))
                content.append('<p class="form-control">')
                
            content.append(self._generate_segment_content(segment, i))
            
            if combine_speaker:
                last_speaker = segment.get("speaker")
                
        content.append("</p></div></div></div>")
        return "\n".join(content)

    def _generate_segment_header(self, segment: Dict, index: int) -> str:
        """Generate header for a transcript segment"""
        timestamp = datetime.fromtimestamp(segment["start"]).strftime("%H:%M:%S")
        return f"""
            <div style="display: block; margin-bottom: 0.5rem;">
                <select onchange="selectChange(this)">
                    <option value="{segment.get('speaker', 'unknown')}" selected="selected">Person {segment.get('speaker', 'unknown')}</option>
                </select>
                <span contenteditable="true">{timestamp}</span>
                <input type="checkbox" class="language" name="language" value="Fremdsprache" style="margin-left: 5px"/>
                <label for="language">Foreign Language</label>
                {self._generate_segment_buttons()}
            </div>
        """

    def _generate_segment_buttons(self) -> str:
        """Generate buttons for segment manipulation"""
        return """
            <button style='float: right;' class='btn btn-danger btn-sm' onclick='removeRow(this)'>
                <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-trash' viewBox='0 0 16 16'>
                    <path d='M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5m3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0z'/>
                    <path d='M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1zM4.118 4 4 4.059V13a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4.059L11.882 4zM2.5 3h11V2h-11z'/>
                </svg>
            </button>
            <button style='float: right;' class='btn btn-primary btn-sm' onclick='addRow(this)'>
                <svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='currentColor' class='bi bi-plus' viewBox='0 0 16 16'>
                    <path d='M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4'/>
                </svg>
            </button>
            <button style="float: right; margin-right: 20px" class="btn btn-warning btn-sm" onclick="tagFunction(this)">
                <svg xmlns="http://www.w3.org/2000/svg" height="16px" viewBox="0 -960 960 960" width="16px" fill="#5f6368">
                    <path d="m264-192 30-120H144l18-72h150l42-168H192l18-72h162l36-144h72l-36 144h144l36-144h72l-36 144h156l-18 72H642l-42 168h168l-18 72H582l-30 120h-72l30-120H366l-30 120h-72Zm120-192h144l42-168H426l-42 168Z"/>
                </svg>
            </button>
        """

    def _generate_segment_content(self, segment: Dict, index: int) -> str:
        """Generate content for a transcript segment"""
        return f"""
            <span id="{index}" tabindex="{index+1}" onclick="changeVideo({index})" contenteditable="true" 
                  class="segment" title="{segment.get('start', 0)} - {segment.get('end', 0)}">
                {segment.get('text', '').strip()}
            </span>
        """

    def _generate_javascript(self, segments: List[Dict], media_url: str, encode_base64: bool) -> str:
        """Generate JavaScript for viewer functionality"""
        return """
        <script>
            // JavaScript implementation would go here
            // Including event handlers, video control, etc.
        </script>
        """