-- Create application user
CREATE USER transcribo_user WITH PASSWORD 'your_secure_password_here';

-- Create application database
CREATE DATABASE transcribo;

-- Grant privileges to application user
ALTER USER transcribo_user WITH SUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE transcribo TO transcribo_user;

-- Connect to the application database
\c transcribo;

-- Create necessary tables
CREATE TABLE IF NOT EXISTS files (
    file_id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    size_bytes BIGINT NOT NULL,
    content_type VARCHAR(100),
    metadata JSONB
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY,
    file_id UUID REFERENCES files(file_id),
    user_id VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    progress FLOAT DEFAULT 0.0,
    metadata JSONB
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);

-- Grant permissions
GRANT ALL ON SCHEMA public TO transcribo_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO transcribo_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO transcribo_user;