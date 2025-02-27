-- Create file_keys table for storing encryption key metadata
CREATE TABLE IF NOT EXISTS file_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL,
    key_reference VARCHAR(255) NOT NULL,  -- Reference to key in Azure Key Vault
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,  -- NULL means no expiration
    version INTEGER NOT NULL DEFAULT 1,   -- For key rotation tracking
    metadata JSONB DEFAULT '{}'::jsonb,   -- Additional metadata (e.g., encryption parameters)
    CONSTRAINT fk_file_keys_file FOREIGN KEY (file_id) REFERENCES files(id) ON DELETE CASCADE
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_file_keys_file_id ON file_keys(file_id);
CREATE INDEX IF NOT EXISTS idx_file_keys_expires_at ON file_keys(expires_at);
CREATE INDEX IF NOT EXISTS idx_file_keys_key_reference ON file_keys(key_reference);

-- Create index for finding latest key version
CREATE INDEX IF NOT EXISTS idx_file_keys_latest ON file_keys(file_id, version DESC);

-- Create function to update version on insert
CREATE OR REPLACE FUNCTION update_file_key_version()
RETURNS TRIGGER AS $$
BEGIN
    SELECT COALESCE(MAX(version), 0) + 1
    INTO NEW.version
    FROM file_keys
    WHERE file_id = NEW.file_id;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to automatically update version
CREATE TRIGGER tr_file_keys_version
    BEFORE INSERT ON file_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_file_key_version();

-- Create function to check key expiration
CREATE OR REPLACE FUNCTION check_file_key_expiration()
RETURNS TRIGGER AS $$
BEGIN
    -- Check if this is the only active key for the file
    IF NOT EXISTS (
        SELECT 1
        FROM file_keys
        WHERE file_id = NEW.file_id
        AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
        AND id != NEW.id
    ) THEN
        -- Don't allow expiration of the only active key
        RAISE EXCEPTION 'Cannot expire the only active key for file %', NEW.file_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger to prevent expiring the only active key
CREATE TRIGGER tr_file_keys_expiration
    BEFORE UPDATE ON file_keys
    FOR EACH ROW
    WHEN (
        OLD.expires_at IS NULL AND 
        NEW.expires_at IS NOT NULL
    )
    EXECUTE FUNCTION check_file_key_expiration();

-- Create view for active keys
CREATE OR REPLACE VIEW active_file_keys AS
SELECT *
FROM file_keys
WHERE expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP
ORDER BY file_id, version DESC;
