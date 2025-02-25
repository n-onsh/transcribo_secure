-- Add composite indexes for time-based queries
CREATE INDEX idx_jobs_status_estimated_time ON jobs (status, estimated_time)
WHERE status IN ('pending', 'processing');

CREATE INDEX idx_jobs_language_estimated_time ON jobs (
    (options->>'language'),
    estimated_time
)
WHERE status IN ('pending', 'processing');

-- Add index for completion time analysis
CREATE INDEX idx_jobs_completion_times ON jobs (
    created_at,
    completed_at
)
WHERE status = 'completed';

-- Add statistics table for time estimates
CREATE TABLE job_time_statistics (
    id SERIAL PRIMARY KEY,
    language VARCHAR(10) NOT NULL,
    duration_seconds FLOAT NOT NULL,
    processing_seconds FLOAT NOT NULL,
    word_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT duration_positive CHECK (duration_seconds > 0),
    CONSTRAINT processing_positive CHECK (processing_seconds > 0),
    CONSTRAINT word_count_positive CHECK (word_count > 0)
);

CREATE INDEX idx_job_stats_language ON job_time_statistics (language);
CREATE INDEX idx_job_stats_duration ON job_time_statistics (duration_seconds);

-- Add function to calculate average processing ratio
CREATE OR REPLACE FUNCTION get_language_processing_ratio(lang VARCHAR)
RETURNS TABLE (
    avg_ratio FLOAT,
    confidence FLOAT,
    sample_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT 
            processing_seconds / duration_seconds as ratio,
            COUNT(*) OVER () as total_samples
        FROM job_time_statistics
        WHERE language = lang
        AND created_at > NOW() - INTERVAL '30 days'
    )
    SELECT 
        AVG(ratio)::FLOAT as avg_ratio,
        LEAST(COUNT(*)::FLOAT / 20, 0.9)::FLOAT as confidence,
        COUNT(*)::INTEGER as sample_count
    FROM stats;
END;
$$ LANGUAGE plpgsql;

-- Add function to update time statistics
CREATE OR REPLACE FUNCTION update_job_statistics()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'completed' AND OLD.status != 'completed' THEN
        -- Calculate actual duration and insert stats
        INSERT INTO job_time_statistics (
            language,
            duration_seconds,
            processing_seconds,
            word_count
        )
        SELECT
            options->>'language',
            EXTRACT(EPOCH FROM (NEW.completed_at - NEW.created_at)),
            EXTRACT(EPOCH FROM (NEW.completed_at - NEW.created_at)),
            (NEW.metadata->>'word_count')::INTEGER
        WHERE NEW.completed_at IS NOT NULL
        AND NEW.created_at IS NOT NULL
        AND NEW.metadata->>'word_count' IS NOT NULL
        AND NEW.options->>'language' IS NOT NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add trigger for statistics updates
CREATE TRIGGER job_completion_stats
    AFTER UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_job_statistics();

-- Add function to estimate processing time
CREATE OR REPLACE FUNCTION estimate_processing_time(
    duration_secs FLOAT,
    lang VARCHAR,
    OUT estimated_seconds FLOAT,
    OUT min_seconds FLOAT,
    OUT max_seconds FLOAT,
    OUT confidence FLOAT
) AS $$
DECLARE
    stats RECORD;
    std_dev FLOAT;
BEGIN
    -- Get language-specific stats
    SELECT * FROM get_language_processing_ratio(lang) INTO stats;
    
    IF stats.sample_count >= 5 THEN
        -- Use language-specific estimate
        estimated_seconds := duration_secs * stats.avg_ratio;
        confidence := stats.confidence;
        
        -- Calculate range using standard deviation
        SELECT STDDEV(processing_seconds / duration_seconds)
        INTO std_dev
        FROM job_time_statistics
        WHERE language = lang
        AND created_at > NOW() - INTERVAL '30 days';
        
        min_seconds := GREATEST(duration_secs, estimated_seconds - (std_dev * estimated_seconds));
        max_seconds := estimated_seconds + (std_dev * estimated_seconds);
    ELSE
        -- Fallback to default estimate
        estimated_seconds := duration_secs * 2;
        confidence := 0.5;
        min_seconds := duration_secs;
        max_seconds := duration_secs * 3;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Add view for job performance analysis
CREATE OR REPLACE VIEW job_performance_metrics AS
SELECT
    options->>'language' as language,
    COUNT(*) as total_jobs,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_processing_time,
    MIN(EXTRACT(EPOCH FROM (completed_at - created_at))) as min_processing_time,
    MAX(EXTRACT(EPOCH FROM (completed_at - created_at))) as max_processing_time,
    AVG((metadata->>'word_count')::INTEGER) as avg_word_count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at)) / (metadata->>'word_count')::INTEGER) as seconds_per_word
FROM jobs
WHERE status = 'completed'
AND completed_at IS NOT NULL
AND created_at IS NOT NULL
AND metadata->>'word_count' IS NOT NULL
GROUP BY options->>'language';

-- Add maintenance function to clean old statistics
CREATE OR REPLACE FUNCTION cleanup_old_statistics()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM job_time_statistics
    WHERE created_at < NOW() - INTERVAL '90 days'
    RETURNING COUNT(*) INTO deleted_count;
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Add comment
COMMENT ON TABLE job_time_statistics IS 'Stores historical job processing statistics for time estimation';
COMMENT ON FUNCTION get_language_processing_ratio IS 'Calculates average processing ratio and confidence for a language';
COMMENT ON FUNCTION estimate_processing_time IS 'Estimates processing time for a given duration and language';
COMMENT ON VIEW job_performance_metrics IS 'Provides performance metrics by language';
