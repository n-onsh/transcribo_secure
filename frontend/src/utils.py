from datetime import datetime, timedelta

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human readable string"""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        return f"{seconds/60:.0f} minutes"
    else:
        return f"{seconds/3600:.1f} hours"

def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human readable string"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def get_status_color(status: str) -> str:
    """Get color class for status"""
    return {
        'pending': 'bg-yellow-100',
        'processing': 'bg-blue-100',
        'completed': 'bg-green-100',
        'failed': 'bg-red-100'
    }.get(status, 'bg-gray-100')

def estimate_completion_time(
    total_jobs: int,
    completed_jobs: int,
    avg_time_per_job: float
) -> datetime:
    """Estimate completion time based on current progress"""
    remaining_jobs = total_jobs - completed_jobs
    estimated_seconds = remaining_jobs * avg_time_per_job
    return datetime.now() + timedelta(seconds=estimated_seconds)