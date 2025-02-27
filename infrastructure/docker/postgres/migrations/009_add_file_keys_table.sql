-- Create file_keys table for encryption key management
CREATE TABLE IF NOT EXISTS file_keys (
    id SERIAL PRIMARY KEY,
    file_id UUID NOT NULL,
    key_reference TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(file_id, key_reference)
);

-- Create index for faster lookups by file_id
CREATE INDEX IF NOT EXISTS idx_file_keys_file_id ON file_keys(file_id);

-- Create index for cleanup of expired keys
CREATE INDEX IF NOT EXISTS idx_file_keys_expires_at ON file_keys(expires_at);

-- Add foreign key constraint to files table
ALTER TABLE file_keys
ADD CONSTRAINT fk_file_keys_file_id
FOREIGN KEY (file_id)
REFERENCES files(id)
ON DELETE CASCADE;

-- Add comment
COMMENT ON TABLE file_keys IS 'Stores metadata about encryption keys for files';
COMMENT ON COLUMN file_keys.file_id IS 'Reference to the file this key belongs to';
COMMENT ON COLUMN file_keys.key_reference IS 'Reference to the key in Key Vault';
COMMENT ON COLUMN file_keys.created_at IS 'When this key was created';
COMMENT ON COLUMN file_keys.expires_at IS 'When this key expires (for key rotation)';
