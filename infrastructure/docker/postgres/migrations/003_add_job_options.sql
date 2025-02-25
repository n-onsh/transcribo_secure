-- Create job_options table
CREATE TABLE IF NOT EXISTS job_options (
    job_id UUID PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    options JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create index for language filtering
CREATE INDEX IF NOT EXISTS idx_job_options_language ON job_options ((options->>'language'));

-- Create trigger to update updated_at
CREATE OR REPLACE FUNCTION update_job_options_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_job_options_updated_at
    BEFORE UPDATE ON job_options
    FOR EACH ROW
    EXECUTE FUNCTION update_job_options_updated_at();

-- Add default options for existing jobs
INSERT INTO job_options (job_id, options)
SELECT id, '{"language": "de", "supported_languages": ["de", "en", "fr", "it"]}'::jsonb
FROM jobs
WHERE id NOT IN (SELECT job_id FROM job_options);
