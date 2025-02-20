# frontend/src/components/editor/editor.py
from nicegui import ui
from typing import Optional
import asyncio
import json
from datetime import datetime

class EditorComponent:
    def __init__(self, api_service):
        self.api = api_service
        self.current_job_id = None
        self.auto_save_task = None
        self.editor_container = None

    async def show_editor(self, job_id: str):
        """Display editor for a specific job"""
        self.current_job_id = job_id
        
        # Create main layout
        with ui.column().classes('w-full max-w-3xl mx-auto'):
            # Header
            with ui.header().classes('w-full bg-blue-600 text-white'):
                ui.label('TranscriboZH Editor')
                
            # Editor container
            self.editor_container = ui.html().classes('w-full')
            
            # Tool bar
            with ui.row().classes('w-full justify-between'):
                ui.button('Save', on_click=self._save_changes).props('no-caps')
                ui.button('Export SRT', on_click=self._export_srt).props('no-caps')
                ui.button('Export Text', on_click=self._export_text).props('no-caps')
            
            # Load editor content
            await self._load_editor_content()
            
            # Start auto-save
            await self._start_auto_save()

    async def _load_editor_content(self):
        """Load editor content from backend"""
        try:
            # Get viewer HTML from backend
            response = await self.api.get_editor_content(self.current_job_id)
            
            # Update editor content
            self.editor_container.set_content(response['content'])
            
            # Add keyboard shortcuts
            await self._setup_keyboard_shortcuts()
            
        except Exception as e:
            ui.notify(f"Error loading editor: {str(e)}", type='error')

    async def _setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts for the editor"""
        js_code = """
        document.addEventListener('keydown', (event) => {
            // Ctrl+Space to play/pause
            if(event.ctrlKey && event.keyCode == 32) {
                event.preventDefault();
                var video = document.getElementById('player');
                if (video.paused) video.play(); 
                else video.pause();
            }
            
            // Tab navigation
            if(event.key === 'Tab') {
                event.preventDefault();
                var segments = document.getElementsByClassName('segment');
                var current = document.activeElement;
                var currentIndex = Array.from(segments).indexOf(current);
                var nextIndex = event.shiftKey ? currentIndex - 1 : currentIndex + 1;
                
                if(nextIndex >= 0 && nextIndex < segments.length) {
                    segments[nextIndex].focus();
                }
            }
        });
        """
        await ui.run_javascript(js_code)

    async def _start_auto_save(self):
        """Start auto-save task"""
        if self.auto_save_task:
            self.auto_save_task.cancel()
            
        self.auto_save_task = asyncio.create_task(self._auto_save_loop())

    async def _auto_save_loop(self):
        """Auto-save loop"""
        while True:
            try:
                await asyncio.sleep(30)  # Save every 30 seconds
                await self._save_changes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                ui.notify(f"Auto-save error: {str(e)}", type='error')

    async def _save_changes(self):
        """Save editor changes"""
        try:
            # Get current editor content
            content = await ui.run_javascript("""
                return document.getElementById('editor').innerHTML;
            """)
            
            # Save to backend
            await self.api.save_editor_content(self.current_job_id, content)
            ui.notify("Changes saved", type='positive')
            
        except Exception as e:
            ui.notify(f"Error saving changes: {str(e)}", type='error')

    async def _export_srt(self):
        """Export as SRT"""
        try:
            response = await self.api.export_srt(self.current_job_id)
            ui.download(content=response['srt'], 
                       filename=f"transcript_{self.current_job_id}.srt")
        except Exception as e:
            ui.notify(f"Error exporting SRT: {str(e)}", type='error')

    async def _export_text(self):
        """Export as text"""
        try:
            response = await self.api.export_text(self.current_job_id)
            ui.download(content=response['text'], 
                       filename=f"transcript_{self.current_job_id}.txt")
        except Exception as e:
            ui.notify(f"Error exporting text: {str(e)}", type='error')

    def cleanup(self):
        """Cleanup tasks"""
        if self.auto_save_task:
            self.auto_save_task.cancel()