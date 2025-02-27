-- Create user if not exists
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'transcribo_user') THEN
    EXECUTE format('CREATE USER transcribo_user WITH PASSWORD %L', current_setting('app.db_user_password'));
  END IF;
END
$$;

-- Create database if not exists
SELECT 'CREATE DATABASE transcribo OWNER transcribo_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'transcribo')\gexec

-- Connect to the database
\c transcribo

-- Create schema and set permissions
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO transcribo_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO transcribo_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO transcribo_user;

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "hstore";

-- Set configuration parameters
ALTER DATABASE transcribo SET timezone TO 'UTC';

-- Create updated_at function
CREATE OR REPLACE FUNCTION update_modified_column() 
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create tables
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    roles TEXT[] DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE TABLE user_keys (
    user_id UUID PRIMARY KEY REFERENCES users(id),
    encrypted_key BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    bucket_type VARCHAR(50) NOT NULL,
    size BIGINT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_owner FOREIGN KEY(owner_id) REFERENCES users(id)
);

CREATE TABLE file_keys (
    file_id UUID PRIMARY KEY REFERENCES files(id),
    encrypted_key BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE file_key_shares (
    file_id UUID NOT NULL REFERENCES files(id),
    user_id UUID NOT NULL REFERENCES users(id),
    encrypted_key BYTEA NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (file_id, user_id)
);

CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL REFERENCES files(id),
    user_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    progress FLOAT NOT NULL DEFAULT 0.0,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    cancelled_at TIMESTAMP WITH TIME ZONE,
    locked_by TEXT,
    locked_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_file FOREIGN KEY(file_id) REFERENCES files(id),
    CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(id),
    CONSTRAINT valid_progress CHECK (progress >= 0.0 AND progress <= 100.0),
    CONSTRAINT valid_retry_count CHECK (retry_count >= 0),
    CONSTRAINT valid_max_retries CHECK (max_retries > 0),
    CONSTRAINT valid_priority CHECK (priority >= 0 AND priority <= 3)
);

CREATE TABLE vocabulary (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(255) NOT NULL,
    terms JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Create indexes
CREATE INDEX idx_job_queue ON jobs (status, priority DESC, next_retry_at)
WHERE status = 'pending';

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

-- Create triggers for updated_at
CREATE TRIGGER update_users_modtime
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_user_keys_modtime
    BEFORE UPDATE ON user_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_files_modtime
    BEFORE UPDATE ON files
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_file_keys_modtime
    BEFORE UPDATE ON file_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_file_key_shares_modtime
    BEFORE UPDATE ON file_key_shares
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_jobs_modtime
    BEFORE UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_vocabulary_modtime
    BEFORE UPDATE ON vocabulary
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- Add trigger for job updates
CREATE TRIGGER job_update_notify
    AFTER UPDATE ON jobs
    FOR EACH ROW
    EXECUTE FUNCTION notify_job_update();

-- Grant permissions
GRANT CONNECT ON DATABASE transcribo TO transcribo_user;
GRANT USAGE ON SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO transcribo_user;
