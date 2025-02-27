-- Add indices for ZIP file handling and job management

-- Index for job parent/child relationships
CREATE INDEX IF NOT EXISTS idx_jobs_parent_id ON jobs ((metadata->>'parent_job_id'));
CREATE INDEX IF NOT EXISTS idx_jobs_child_jobs ON jobs USING GIN ((metadata->'child_jobs'));

-- Index for job type filtering
CREATE INDEX IF NOT EXISTS idx_jobs_type ON jobs (job_type);

-- Index for job status and progress tracking
CREATE INDEX IF NOT EXISTS idx_jobs_stage ON jobs ((metadata->>'stage'));
CREATE INDEX IF NOT EXISTS idx_jobs_progress ON jobs ((metadata->>'progress'));

-- Index for job ownership
CREATE INDEX IF NOT EXISTS idx_jobs_owner_id ON jobs (owner_id);

-- Index for file metadata
CREATE INDEX IF NOT EXISTS idx_files_job_id ON files ((metadata->>'job_id'));
CREATE INDEX IF NOT EXISTS idx_files_is_combined ON files ((metadata->>'is_combined'));
CREATE INDEX IF NOT EXISTS idx_files_source_files ON files USING GIN ((metadata->'source_files'));

-- Index for file encryption status
CREATE INDEX IF NOT EXISTS idx_files_encrypted ON files ((metadata->>'encrypted'));

-- Index for file content type
CREATE INDEX IF NOT EXISTS idx_files_content_type ON files ((metadata->>'content_type'));

-- Index for file size
CREATE INDEX IF NOT EXISTS idx_files_size ON files ((metadata->>'size'));

-- Comment explaining the indices
COMMENT ON INDEX idx_jobs_parent_id IS 'Improves performance of job relationship queries';
COMMENT ON INDEX idx_jobs_child_jobs IS 'Enables efficient lookup of child jobs';
COMMENT ON INDEX idx_jobs_type IS 'Optimizes filtering by job type';
COMMENT ON INDEX idx_jobs_stage IS 'Improves job progress tracking queries';
COMMENT ON INDEX idx_jobs_progress IS 'Enables efficient progress filtering';
COMMENT ON INDEX idx_jobs_owner_id IS 'Optimizes user-specific job queries';
COMMENT ON INDEX idx_files_job_id IS 'Links files to their processing jobs';
COMMENT ON INDEX idx_files_is_combined IS 'Identifies combined audio files';
COMMENT ON INDEX idx_files_source_files IS 'Tracks relationships between original and combined files';
COMMENT ON INDEX idx_files_encrypted IS 'Enables filtering by encryption status';
COMMENT ON INDEX idx_files_content_type IS 'Improves file type filtering';
COMMENT ON INDEX idx_files_size IS 'Enables size-based queries and sorting';
