-- First connect as superuser
\c postgres

-- Then create our application user and database
CREATE USER transcribo_user WITH PASSWORD '${POSTGRES_PASSWORD}';
CREATE DATABASE transcribo OWNER transcribo_user;

-- Connect to new database
\c transcribo

-- Create schema and set permissions
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO transcribo_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO transcribo_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO transcribo_user;

-- Enable extensions in the new database
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "hstore";

-- Set configuration parameters
ALTER DATABASE transcribo SET timezone TO 'UTC';

-- Create function for updating timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Verify setup
DO $$
BEGIN
    -- Verify user exists
    IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'transcribo_user') THEN
        RAISE EXCEPTION 'Database user was not created properly';
    END IF;

    -- Verify schema exists
    IF NOT EXISTS (SELECT FROM information_schema.schemata WHERE schema_name = 'public') THEN
        RAISE EXCEPTION 'Schema was not created properly';
    END IF;
END
$$;

-- Grant final permissions
GRANT CONNECT ON DATABASE transcribo TO transcribo_user;
GRANT USAGE ON SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO transcribo_user;