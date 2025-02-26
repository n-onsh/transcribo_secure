// Editor state
let state = {
    player: null,
    isDirty: false,
    lastSaved: null,
    currentSegment: null
};

// Initialize editor
document.addEventListener('DOMContentLoaded', () => {
    initializePlayer();
    initializeEventListeners();
    loadEditorState();
});

// Player initialization
function initializePlayer() {
    state.player = document.getElementById('media-player');
    
    // Playback rate control
    document.getElementById('speed-control').addEventListener('change', (e) => {
        state.player.playbackRate = parseFloat(e.target.value);
    });
    
    // Jump back control
    const jumpBack = document.getElementById('delay-control');
    document.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && e.ctrlKey) {
            e.preventDefault();
            if (state.player.paused) {
                state.player.play();
            } else {
                state.player.pause();
            }
        } else if (e.code === 'ArrowLeft' && e.ctrlKey) {
            e.preventDefault();
            state.player.currentTime -= parseInt(jumpBack.value);
        }
    });
}

// Event listeners
function initializeEventListeners() {
    // Save button
    document.getElementById('save-btn').addEventListener('click', saveEditorState);
    
    // Export buttons
    document.getElementById('export-viewer-btn')?.addEventListener('click', () => exportTranscription('viewer'));
    document.getElementById('export-text-btn')?.addEventListener('click', () => exportTranscription('text'));
    document.getElementById('export-srt-btn')?.addEventListener('click', () => exportTranscription('srt'));
    
    // Speaker names
    document.querySelectorAll('.speaker-name').forEach(input => {
        input.addEventListener('input', () => {
            updateSpeakerName(input.dataset.speakerId, input.value);
            markDirty();
        });
    });
    
    // Speaker selects
    document.querySelectorAll('.speaker-select').forEach(select => {
        select.addEventListener('change', () => {
            updateSegmentSpeaker(select.dataset.segmentId, select.value);
            markDirty();
        });
    });
    
    // Foreign checkboxes
    document.querySelectorAll('.foreign-checkbox').forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            updateSegmentLanguage(checkbox.dataset.segmentId, checkbox.checked);
            markDirty();
        });
    });
    
    // Segment text
    document.querySelectorAll('.segment-text').forEach(div => {
        div.addEventListener('input', () => {
            updateSegmentText(div.dataset.segmentId, div.innerText);
            markDirty();
        });
        div.addEventListener('focus', () => {
            state.currentSegment = div.dataset.segmentId;
            highlightSegment(div.dataset.segmentId);
        });
        div.addEventListener('click', () => {
            const start = parseFloat(div.parentElement.dataset.start);
            state.player.currentTime = start;
        });
    });
    
    // Segment actions
    document.querySelectorAll('.delete-segment').forEach(btn => {
        btn.addEventListener('click', () => {
            const segment = btn.closest('.segment');
            deleteSegment(segment.dataset.segmentId);
            markDirty();
        });
    });
    
    document.querySelectorAll('.split-segment').forEach(btn => {
        btn.addEventListener('click', () => {
            const segment = btn.closest('.segment');
            splitSegment(segment.dataset.segmentId);
            markDirty();
        });
    });
    
    document.querySelectorAll('.merge-up').forEach(btn => {
        btn.addEventListener('click', () => {
            const segment = btn.closest('.segment');
            mergeSegmentUp(segment.dataset.segmentId);
            markDirty();
        });
    });
    
    // Navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            e.preventDefault();
            navigateSegments(e.shiftKey ? -1 : 1);
        }
    });
}

// State management
async function loadEditorState() {
    try {
        // Check if we're in standalone mode
        if (window.location.protocol === 'file:') {
            // Load from localStorage
            const savedState = localStorage.getItem('editorState');
            if (savedState) {
                const state = JSON.parse(savedState);
                applyEditorState(state);
            }
            return;
        }

        // Load from server
        const response = await fetch(`/api/editor/state/${EDITOR_CONFIG.jobId}`);
        if (response.ok) {
            const savedState = await response.json();
            if (savedState.lastSaved > EDITOR_CONFIG.timestamp) {
                applyEditorState(savedState);
            }
        }
    } catch (error) {
        console.error('Failed to load editor state:', error);
    }
}

async function saveEditorState() {
    try {
        const currentState = {
            speakers: Array.from(document.querySelectorAll('.speaker-name')).map(input => ({
                id: input.dataset.speakerId,
                name: input.value
            })),
            segments: Array.from(document.querySelectorAll('.segment')).map(div => ({
                id: div.dataset.segmentId,
                speakerId: div.querySelector('.speaker-select')?.value,
                text: div.querySelector('.segment-text').innerText,
                start: parseFloat(div.dataset.start),
                end: parseFloat(div.dataset.end),
                isForeign: div.querySelector('.foreign-checkbox')?.checked
            })),
            lastSaved: new Date().toISOString()
        };

        // Check if we're in standalone mode
        if (window.location.protocol === 'file:') {
            // Save to localStorage
            localStorage.setItem('editorState', JSON.stringify(currentState));
            state.isDirty = false;
            state.lastSaved = currentState.lastSaved;
            return;
        }
        
        // Save to server
        const response = await fetch(`/api/editor/state/${EDITOR_CONFIG.jobId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentState)
        });
        
        if (response.ok) {
            state.isDirty = false;
            state.lastSaved = currentState.lastSaved;
        }
    } catch (error) {
        console.error('Failed to save editor state:', error);
    }
}

function applyEditorState(savedState) {
    // Update speakers
    savedState.speakers.forEach(speaker => {
        const input = document.querySelector(`[data-speaker-id="${speaker.id}"]`);
        if (input) input.value = speaker.name;
    });
    
    // Update segments
    savedState.segments.forEach(segment => {
        const div = document.querySelector(`[data-segment-id="${segment.id}"]`);
        if (div) {
            div.querySelector('.speaker-select').value = segment.speakerId;
            div.querySelector('.segment-text').innerText = segment.text;
            const checkbox = div.querySelector('.foreign-checkbox');
            if (checkbox) checkbox.checked = segment.isForeign;
        }
    });
    
    state.lastSaved = savedState.lastSaved;
}

// Segment operations
function updateSpeakerName(speakerId, name) {
    document.querySelectorAll('.speaker-select').forEach(select => {
        const option = select.querySelector(`option[value="${speakerId}"]`);
        if (option) option.textContent = name;
    });
}

function updateSegmentSpeaker(segmentId, speakerId) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (segment) {
        segment.querySelector('.speaker-select').value = speakerId;
    }
}

function updateSegmentText(segmentId, text) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (segment) {
        segment.querySelector('.segment-text').innerText = text;
    }
}

function updateSegmentLanguage(segmentId, isForeign) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (segment) {
        const checkbox = segment.querySelector('.foreign-checkbox');
        if (checkbox) checkbox.checked = isForeign;
    }
}

function deleteSegment(segmentId) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (segment && confirm('Are you sure you want to delete this segment?')) {
        segment.remove();
    }
}

function splitSegment(segmentId) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (!segment) return;
    
    const selection = window.getSelection();
    if (!selection.rangeCount) return;
    
    const range = selection.getRangeAt(0);
    const textNode = range.startContainer;
    if (!segment.contains(textNode)) return;
    
    const template = document.getElementById('segment-template');
    const newSegment = template.content.cloneNode(true).firstElementChild;
    
    const start = parseFloat(segment.dataset.start);
    const end = parseFloat(segment.dataset.end);
    const splitPoint = start + (end - start) * (range.startOffset / textNode.length);
    
    segment.dataset.end = splitPoint;
    newSegment.dataset.start = splitPoint;
    newSegment.dataset.end = end;
    newSegment.dataset.segmentId = `segment-${Date.now()}`;
    
    const beforeText = textNode.textContent.substring(0, range.startOffset);
    const afterText = textNode.textContent.substring(range.startOffset);
    
    segment.querySelector('.segment-text').innerText = beforeText;
    newSegment.querySelector('.segment-text').innerText = afterText;
    newSegment.querySelector('.speaker-select').value = segment.querySelector('.speaker-select').value;
    
    segment.after(newSegment);
    initializeEventListeners();
}

function mergeSegmentUp(segmentId) {
    const segment = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (!segment) return;
    
    const prevSegment = segment.previousElementSibling;
    if (!prevSegment) return;
    
    prevSegment.querySelector('.segment-text').innerText += ' ' + segment.querySelector('.segment-text').innerText;
    prevSegment.dataset.end = segment.dataset.end;
    segment.remove();
}

function highlightSegment(segmentId) {
    document.querySelectorAll('.segment').forEach(div => {
        div.style.backgroundColor = div.dataset.segmentId === segmentId ? '#e3f2fd' : '';
    });
}

function navigateSegments(direction) {
    const segments = Array.from(document.querySelectorAll('.segment-text'));
    const currentIndex = segments.findIndex(div => div.dataset.segmentId === state.currentSegment);
    if (currentIndex === -1) return;
    
    const nextIndex = (currentIndex + direction + segments.length) % segments.length;
    segments[nextIndex].focus();
}

// Export operations
async function exportTranscription(format) {
    // In standalone mode, export locally
    if (window.location.protocol === 'file:') {
        const segments = Array.from(document.querySelectorAll('.segment'))
            .map(segment => ({
                start: parseFloat(segment.dataset.start),
                end: parseFloat(segment.dataset.end),
                text: segment.querySelector('.segment-text').textContent,
                speaker: segment.querySelector('.speaker-label').textContent
            }));

        let content = '';
        if (format === 'text') {
            content = segments.map(s => `${s.speaker}: ${s.text}`).join('\n\n');
        } else if (format === 'srt') {
            content = segments.map((s, i) => {
                const start = new Date(s.start * 1000).toISOString().substr(11, 12).replace('.', ',');
                const end = new Date(s.end * 1000).toISOString().substr(11, 12).replace('.', ',');
                return `${i + 1}\n${start} --> ${end}\n${s.speaker}: ${s.text}\n`;
            }).join('\n');
        }

        // Create and download file
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcription.${format}`;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
        return;
    }

    try {
        const response = await fetch(`/api/editor/${EDITOR_CONFIG.jobId}/export/${format}`);
        if (!response.ok) {
            throw new Error(`Failed to export as ${format}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `transcription.${format}`;
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        a.remove();
    } catch (error) {
        console.error(`Error exporting as ${format}:`, error);
        alert(`Failed to export as ${format}`);
    }
}

// Utility functions
function markDirty() {
    state.isDirty = true;
    document.getElementById('save-btn').style.backgroundColor = '#dc3545';
}

// Cleanup
window.addEventListener('beforeunload', (e) => {
    if (state.isDirty) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
    }
});
