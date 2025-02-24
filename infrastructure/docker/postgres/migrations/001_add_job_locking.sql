-- Add job locking columns
ALTER TABLE jobs
ADD COLUMN locked_by TEXT,
ADD COLUMN locked_at TIMESTAMP WITH TIME ZONE;

-- Add index for job queue
CREATE INDEX idx_job_queue ON jobs (status, priority DESC, next_retry_at)
WHERE status = 'pending';

-- Add index for worker health monitoring
CREATE INDEX idx_job_locks ON jobs (locked_by, locked_at)
WHERE locked_by IS NOT NULL;

-- Add function to release stale locks
CREATE OR REPLACE FUNCTION release_stale_job_locks(max_lock_duration_minutes INTEGER)
RETURNS INTEGER AS $$
DECLARE
    released_count INTEGER;
BEGIN
    WITH updated_jobs AS (
        UPDATE jobs
        SET 
            status = 'pending',
            locked_by = NULL,
            locked_at = NULL,
            retry_count = LEAST(retry_count + 1, max_retries),
            next_retry_at = CASE 
                WHEN retry_count < max_retries THEN NOW() + (INTERVAL '1 minute' * POWER(2, retry_count))
                ELSE NULL
            END
        WHERE 
            status = 'processing'
            AND locked_by IS NOT NULL
            AND locked_at < NOW() - (max_lock_duration_minutes * INTERVAL '1 minute')
        RETURNING id
    )
    SELECT COUNT(*) INTO released_count FROM updated_jobs;

    RETURN released_count;
END;
$$ LANGUAGE plpgsql;

-- Add function to notify job updates
CREATE OR REPLACE FUNCTION notify_job_update()
RETURNS TRIGGER AS $$
BEGIN
    -- Notify on job status changes
    IF OLD.status IS NULL OR NEW.status != OLD.status THEN
        PERFORM pg_notify(
            'job_updates',
            json_build_object(
                'job_id', NEW.id,
                'status', NEW.status,
                'user_id', NEW.user_id
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for job updates
CREATE TRIGGER job_update_notify
    AFTER UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION notify_job_update();

-- Add comments
COMMENT ON COLUMN jobs.locked_by IS 'ID of the worker that claimed this job';
COMMENT ON COLUMN jobs.locked_at IS 'Timestamp when the job was claimed';
COMMENT ON INDEX idx_job_queue IS 'Index for efficient job queue processing';
COMMENT ON INDEX idx_job_locks IS 'Index for monitoring worker locks';
COMMENT ON FUNCTION release_stale_job_locks IS 'Release locks from failed workers';
COMMENT ON FUNCTION notify_job_update IS 'Notify listeners of job status changes';
