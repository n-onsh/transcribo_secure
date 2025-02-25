-- Rename columns in files table
ALTER TABLE files RENAME COLUMN user_id TO owner_id;
ALTER TABLE files RENAME COLUMN type TO bucket_type;

-- Update foreign key constraint name for clarity
ALTER TABLE files DROP CONSTRAINT fk_user;
ALTER TABLE files ADD CONSTRAINT fk_owner FOREIGN KEY(owner_id) REFERENCES users(id);
