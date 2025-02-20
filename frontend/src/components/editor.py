from nicegui import ui
from ..services.auth import AuthService
from ..services.api import APIService
import logging
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Initialize services
auth_service = AuthService()
api_service = APIService()

@ui.page('/editor/{job_id}')
async def editor(job_id: str):
    """Editor page with authentication"""
    try:
        # Check authentication
        if not await auth_service.ensure_authenticated():
            return
            
        # Get transcription data
        transcription = await api_service.get_transcription(job_id)
        if not transcription:
            ui.notify("Transcription not found", type="error")
            ui.open("/")
            return
            
        with ui.column():
            # Header
            with ui.header(elevated=True).style("background-color: #0070b4;").classes("q-pa-xs-xs"):
                with ui.row().classes("w-full items-center justify-between"):
                    # Logo
                    ui.image(str(Path(__file__).parent.parent / "data" / "banner.png")).style(
                        "height: 90px; width: 443px;"
                    )
                    
                    # Navigation
                    with ui.row():
                        ui.button(
                            "Back to Dashboard",
                            on_click=lambda: ui.open("/")
                        ).props("no-caps")
                        ui.button(
                            icon="account_circle",
                            on_click=lambda: ui.open("/logout")
                        ).props("flat")

            # Editor content
            with ui.row():
                # Left column - Audio/Video player and metadata
                with ui.column().classes("w-1/3"):
                    with ui.card().classes("w-full p-4"):
                        # Media player
                        if transcription.get("media_type") == "video":
                            ui.video(transcription["media_url"]).classes("w-full")
                        else:
                            ui.audio(transcription["media_url"])
                            
                        # Metadata
                        ui.markdown("### File Information")
                        ui.label(f"File: {transcription['file_name']}")
                        ui.label(f"Duration: {transcription['duration']:.2f} seconds")
                        ui.label(f"Created: {transcription['created_at']}")
                        
                        # Playback controls
                        ui.number("Delay (seconds)", value=0, min=0, max=10, step=0.5).bind_value(
                            app.storage.user, "playback_delay"
                        )
                        
                        # Speaker management
                        ui.markdown("### Speakers")
                        for idx, speaker in enumerate(transcription["speakers"]):
                            with ui.row():
                                ui.input(
                                    f"Speaker {idx + 1}",
                                    value=speaker["name"]
                                ).bind_value_to(
                                    speaker, "name",
                                    lambda s: handle_speaker_change(job_id, idx, s)
                                )

                # Right column - Transcript editor
                with ui.column().classes("w-2/3"):
                    with ui.card().classes("w-full p-4"):
                        # Toolbar
                        with ui.row():
                            ui.button(
                                "Save",
                                on_click=lambda: handle_save(job_id)
                            ).props("no-caps")
                            ui.button(
                                "Download Editor",
                                on_click=lambda: handle_download(job_id)
                            ).props("no-caps")
                            ui.button(
                                "Download SRT",
                                on_click=lambda: handle_download_srt(job_id)
                            ).props("no-caps")
                            
                            # Language filter
                            ui.checkbox(
                                "Remove foreign languages on export"
                            ).bind_value(
                                app.storage.user,
                                "remove_foreign_languages"
                            )
                            
                        # Segments
                        for segment in transcription["segments"]:
                            with ui.card().classes("w-full mb-2 p-2"):
                                with ui.row():
                                    # Speaker selection
                                    ui.select(
                                        options=[
                                            (i, f"Speaker {i+1}")
                                            for i in range(len(transcription["speakers"]))
                                        ],
                                        value=segment["speaker_idx"]
                                    ).bind_value_to(
                                        segment, "speaker_idx",
                                        lambda s, seg=segment: handle_segment_speaker(job_id, seg["id"], s)
                                    )
                                    
                                    # Timestamp
                                    ui.label(f"{segment['start']:.2f}s - {segment['end']:.2f}s")
                                    
                                    # Language flag
                                    if segment.get("is_foreign_language"):
                                        ui.checkbox(
                                            "Foreign language"
                                        ).bind_value_to(
                                            segment, "is_foreign_language",
                                            lambda f, seg=segment: handle_segment_language(job_id, seg["id"], f)
                                        ).props("checked")
                                    
                                    # Segment controls
                                    ui.button(
                                        icon="delete",
                                        on_click=lambda seg=segment: handle_delete_segment(job_id, seg["id"])
                                    ).props("flat")
                                    ui.button(
                                        icon="add",
                                        on_click=lambda seg=segment: handle_add_segment(job_id, seg["id"])
                                    ).props("flat")
                                
                                # Text editor
                                ui.textarea(
                                    value=segment["text"]
                                ).bind_value_to(
                                    segment, "text",
                                    lambda t, seg=segment: handle_segment_text(job_id, seg["id"], t)
                                ).classes("w-full")

    except Exception as e:
        logger.error(f"Error loading editor: {str(e)}")
        ui.notify("Error loading editor", type="error")
        ui.open("/")

async def handle_save(job_id: str):
    """Save editor changes"""
    try:
        await api_service.save_transcription(job_id)
        ui.notify("Changes saved successfully")
    except Exception as e:
        logger.error(f"Failed to save changes: {str(e)}")
        ui.notify("Failed to save changes", type="error")

async def handle_download(job_id: str):
    """Download editor HTML"""
    try:
        result = await api_service.get_transcription(job_id)
        ui.download(content=result["editor_html"], filename=f"editor_{job_id}.html")
    except Exception as e:
        logger.error(f"Failed to download editor: {str(e)}")
        ui.notify("Failed to download editor", type="error")

async def handle_download_srt(job_id: str):
    """Download SRT file"""
    try:
        result = await api_service.get_transcription(job_id)
        ui.download(content=result["srt"], filename=f"transcript_{job_id}.srt")
    except Exception as e:
        logger.error(f"Failed to download SRT: {str(e)}")
        ui.notify("Failed to download SRT", type="error")

async def handle_speaker_change(job_id: str, speaker_idx: int, name: str):
    """Handle speaker name change"""
    try:
        await api_service.update_speaker(job_id, speaker_idx, name)
    except Exception as e:
        logger.error(f"Failed to update speaker: {str(e)}")
        ui.notify("Failed to update speaker", type="error")

async def handle_segment_speaker(job_id: str, segment_id: str, speaker_idx: int):
    """Handle segment speaker change"""
    try:
        await api_service.update_segment(job_id, segment_id, {"speaker_idx": speaker_idx})
    except Exception as e:
        logger.error(f"Failed to update segment speaker: {str(e)}")
        ui.notify("Failed to update segment", type="error")

async def handle_segment_text(job_id: str, segment_id: str, text: str):
    """Handle segment text change"""
    try:
        await api_service.update_segment(job_id, segment_id, {"text": text})
    except Exception as e:
        logger.error(f"Failed to update segment text: {str(e)}")
        ui.notify("Failed to update segment", type="error")

async def handle_segment_language(job_id: str, segment_id: str, is_foreign: bool):
    """Handle segment language flag change"""
    try:
        await api_service.update_segment(job_id, segment_id, {"is_foreign_language": is_foreign})
    except Exception as e:
        logger.error(f"Failed to update segment language: {str(e)}")
        ui.notify("Failed to update segment", type="error")

async def handle_delete_segment(job_id: str, segment_id: str):
    """Handle segment deletion"""
    try:
        if await ui.confirm("Delete this segment?"):
            await api_service.delete_segment(job_id, segment_id)
            ui.notify("Segment deleted")
            ui.refresh()
    except Exception as e:
        logger.error(f"Failed to delete segment: {str(e)}")
        ui.notify("Failed to delete segment", type="error")

async def handle_add_segment(job_id: str, after_id: str):
    """Handle adding new segment"""
    try:
        await api_service.add_segment(job_id, after_id)
        ui.notify("Segment added")
        ui.refresh()
    except Exception as e:
        logger.error(f"Failed to add segment: {str(e)}")
        ui.notify("Failed to add segment", type="error")
