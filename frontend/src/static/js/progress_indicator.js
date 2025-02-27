// Progress indicator functionality
document.addEventListener('DOMContentLoaded', function() {
    const progressTracker = document.querySelector('.progress-tracker');
    if (!progressTracker) return;

    // Hide initially
    progressTracker.style.display = 'none';

    // Listen for progress updates
    progressTracker.addEventListener('progress-update', function(event) {
        const data = event.detail;
        
        // Update stage icons
        document.querySelectorAll('.progress-stage').forEach(stage => {
            const stageId = stage.getAttribute('data-stage-id');
            const stageIcon = stage.querySelector('.stage-icon');
            
            if (stageId === data.stage) {
                stageIcon.classList.add('active');
                stageIcon.classList.remove('completed');
            } else if (data.completed_stages.includes(stageId)) {
                stageIcon.classList.add('completed');
                stageIcon.classList.remove('active');
            } else {
                stageIcon.classList.remove('active', 'completed');
            }
        });
        
        // Update current stage name and progress
        const currentStage = document.querySelector(`.progress-stage[data-stage-id="${data.stage}"]`);
        if (currentStage) {
            const stageName = currentStage.querySelector('.stage-name').textContent;
            const stageIcon = currentStage.querySelector('.stage-icon i')?.className || 'bi bi-arrow-right-circle';
            
            const currentStageInfo = document.querySelector('.current-stage-progress span:first-child');
            currentStageInfo.innerHTML = `<i class="${stageIcon} me-2"></i>${stageName}`;
            
            const progressBadge = document.querySelector('.current-stage-progress .badge');
            progressBadge.textContent = `${Math.round(data.progress)}%`;
            
            const progressBar = document.querySelector('.current-stage-progress .progress-bar');
            progressBar.style.width = `${data.progress}%`;
            progressBar.setAttribute('aria-valuenow', data.progress);
        }
        
        // Update estimated time if provided
        if (data.estimated_time) {
            const timeDiv = document.querySelector('.progress-info div:first-child');
            timeDiv.innerHTML = `
                <i class="bi bi-clock me-1"></i>
                Estimated time: ${formatTime(data.estimated_time)}
            `;
        }
        
        // Update resource usage if provided
        if (data.resource_usage) {
            const resourceDiv = document.querySelector('.progress-info div:last-child');
            resourceDiv.innerHTML = `
                <i class="bi bi-cpu me-1"></i>
                CPU: ${Math.round(data.resource_usage.cpu)}%
                <i class="bi bi-memory me-1 ms-2"></i>
                Memory: ${Math.round(data.resource_usage.memory)}%
            `;
        }
    });

    function formatTime(seconds) {
        if (seconds < 60) {
            return `${seconds} seconds`;
        } else if (seconds < 3600) {
            const minutes = Math.floor(seconds / 60);
            return `${minutes} minute${minutes !== 1 ? 's' : ''}`;
        } else {
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            if (minutes === 0) {
                return `${hours} hour${hours !== 1 ? 's' : ''}`;
            }
            return `${hours} hour${hours !== 1 ? 's' : ''} ${minutes} minute${minutes !== 1 ? 's' : ''}`;
        }
    }
});
