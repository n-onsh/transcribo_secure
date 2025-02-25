-- Add time estimation columns to jobs table
ALTER TABLE jobs
ADD COLUMN estimated_time FLOAT,
ADD COLUMN estimated_range_min FLOAT,
ADD COLUMN estimated_range_max FLOAT,
ADD COLUMN estimate_confidence FLOAT;

-- Add constraints
ALTER TABLE jobs
ADD CONSTRAINT jobs_estimated_time_check CHECK (estimated_time >= 0),
ADD CONSTRAINT jobs_estimated_range_min_check CHECK (estimated_range_min >= 0),
ADD CONSTRAINT jobs_estimated_range_max_check CHECK (estimated_range_max >= 0),
ADD CONSTRAINT jobs_estimate_confidence_check CHECK (estimate_confidence >= 0 AND estimate_confidence <= 1),
ADD CONSTRAINT jobs_estimated_range_check CHECK (estimated_range_min <= estimated_range_max);

-- Add index for time estimation queries
CREATE INDEX idx_jobs_estimated_time ON jobs (estimated_time);

-- Add comment
COMMENT ON COLUMN jobs.estimated_time IS 'Estimated processing time in seconds';
COMMENT ON COLUMN jobs.estimated_range_min IS 'Minimum estimated processing time in seconds';
COMMENT ON COLUMN jobs.estimated_range_max IS 'Maximum estimated processing time in seconds';
COMMENT ON COLUMN jobs.estimate_confidence IS 'Confidence level of time estimate (0-1)';
