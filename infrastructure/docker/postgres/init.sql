-- Create user if not exists
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'transcribo_user') THEN
    CREATE USER transcribo_user WITH PASSWORD 'your_secure_password';
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

-- Grant permissions
GRANT CONNECT ON DATABASE transcribo TO transcribo_user;
GRANT USAGE ON SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO transcribo_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO transcribo_user;