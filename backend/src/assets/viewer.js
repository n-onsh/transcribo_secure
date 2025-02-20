// Viewer state
let state = {
    player: null,
    currentSegment: null,
    options: VIEWER_CONFIG.options,
    isRefreshing: false
};

// Initialize viewer
document.addEventListener('DOMContentLoaded', () => {
    initializePlayer();
    initializeEventListeners();
    initializeOptions();
});

// Player initialization
function initializePlayer() {
    state.player = document.getElementById('audio-player');
    
    // Playback rate control
    document.getElementById('playback-rate').addEventListener('change', (e) => {
        state.player.playbackRate = parseFloat(e.target.value);
    });
    
    // Track current time
    state.player.addEventListener('timeupdate', () => {
        highlightCurrentSegment();
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.code === 'Space' && e.ctrlKey) {
            e.preventDefault();
            if (state.player.paused) {
                state.player.play();
            } else {
                state.player.pause();
            }
        }
    });
}

// Event listeners
function initializeEventListeners() {
    // Export buttons
    document.getElementById('export-txt-btn').addEventListener('click', exportText);
    document.getElementById('export-srt-btn').addEventListener('click', exportSRT);
    document.getElementById('open-editor-btn').addEventListener('click', openEditor);
    
    // Segment clicks
    document.querySelectorAll('.segment-text').forEach(div => {
        div.addEventListener('click', () => {
            const start = parseFloat(div.dataset.start);
            state.player.currentTime = start;
            state.player.play();
        });
    });
}

// Options initialization
function initializeOptions() {
    // Combine speakers
    const combineCheckbox = document.getElementById('combine-speakers');
    combineCheckbox.addEventListener('change', () => {
        state.options.combine_speakers = combineCheckbox.checked;
        refreshViewer();
    });
    
    // Show timestamps
    const timestampCheckbox = document.getElementById('show-timestamps');
    timestampCheckbox.addEventListener('change', () => {
        state.options.show_timestamps = timestampCheckbox.checked;
        refreshViewer();
    });
    
    // Include foreign
    const foreignCheckbox = document.getElementById('include-foreign');
    foreignCheckbox.addEventListener('change', () => {
        state.options.include_foreign = foreignCheckbox.checked;
        refreshViewer();
    });
}

// Segment highlighting
function highlightCurrentSegment() {
    if (state.isRefreshing) return;
    
    const currentTime = state.player.currentTime;
    const segments = document.querySelectorAll('.segment-text');
    
    let foundCurrent = false;
    segments.forEach(div => {
        const start = parseFloat(div.dataset.start);
        const end = parseFloat(div.dataset.end);
        
        if (currentTime >= start && currentTime < end) {
            if (state.currentSegment !== div) {
                unhighlightSegments();
                highlightSegment(div);
                scrollToSegment(div);
                state.currentSegment = div;
            }
            foundCurrent = true;
        }
    });
    
    if (!foundCurrent && state.currentSegment) {
        unhighlightSegments();
        state.currentSegment = null;
    }
}

function highlightSegment(segment) {
    segment.style.backgroundColor = '#e3f2fd';
}

function unhighlightSegments() {
    document.querySelectorAll('.segment-text').forEach(div => {
        div.style.backgroundColor = '';
    });
}

function scrollToSegment(segment) {
    const container = document.querySelector('.content');
    const containerRect = container.getBoundingClientRect();
    const segmentRect = segment.getBoundingClientRect();
    
    if (segmentRect.top < containerRect.top || segmentRect.bottom > containerRect.bottom) {
        segment.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}

// Viewer refresh
async function refreshViewer() {
    try {
        state.isRefreshing = true;
        
        const response = await fetch(`/api/transcription/${VIEWER_CONFIG.jobId}/viewer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ options: state.options })
        });
        
        if (response.ok) {
            const html = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Update transcript
            const oldTranscript = document.querySelector('.transcript-container');
            const newTranscript = doc.querySelector('.transcript-container');
            oldTranscript.replaceWith(newTranscript);
            
            // Reinitialize event listeners
            initializeEventListeners();
            
            // Restore player state
            const currentTime = state.player.currentTime;
            const isPaused = state.player.paused;
            state.player.currentTime = currentTime;
            if (!isPaused) state.player.play();
        }
    } catch (error) {
        console.error('Failed to refresh viewer:', error);
    } finally {
        state.isRefreshing = false;
    }
}

// Export operations
async function exportText() {
    try {
        const response = await fetch(`/api/transcription/${VIEWER_CONFIG.jobId}/text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ options: state.options })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${VIEWER_CONFIG.jobId}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch (error) {
        console.error('Failed to export text:', error);
    }
}

async function exportSRT() {
    try {
        const response = await fetch(`/api/transcription/${VIEWER_CONFIG.jobId}/srt`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ options: state.options })
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${VIEWER_CONFIG.jobId}.srt`;
            a.click();
            URL.revokeObjectURL(url);
        }
    } catch (error) {
        console.error('Failed to export SRT:', error);
    }
}

function openEditor() {
    window.location.href = `/editor/${VIEWER_CONFIG.jobId}`;
}
