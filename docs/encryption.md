# File Encryption System

The file encryption system provides secure storage of files using authenticated encryption with AES-256-GCM. The system includes key management, secure key storage, and automatic key rotation.

## Architecture

The encryption system consists of three main components:

1. **Key Vault Service**: Manages secure storage of encryption keys
   - Supports both Azure Key Vault and local development mode
   - Handles key storage, retrieval, and deletion
   - Includes caching for performance optimization

2. **File Key Service**: Manages encryption keys for files
   - Generates and tracks encryption keys
   - Handles key rotation and expiration
   - Stores key metadata in the database

3. **Encryption Service**: Performs file encryption/decryption
   - Uses AES-256-GCM for authenticated encryption
   - Supports streaming for large files
   - Handles key rotation transparently

## Configuration

Configuration is managed through environment variables:

```env
# Encryption settings
ENCRYPTION_ENABLED=true
ENCRYPTION_ALGORITHM=AES-256-GCM
ENCRYPTION_KEY_ROTATION_DAYS=30
ENCRYPTION_CHUNK_SIZE_MB=5

# Key Vault settings
KEY_VAULT_ENABLED=true
KEY_VAULT_MODE=local  # local or azure
KEY_VAULT_URL=  # Required for azure mode
KEY_VAULT_TENANT_ID=  # Required for azure mode
KEY_VAULT_CLIENT_ID=  # Required for azure mode
KEY_VAULT_CLIENT_SECRET=  # Required for azure mode
KEY_VAULT_CACHE_ENABLED=true
KEY_VAULT_CACHE_DURATION_MINUTES=60
KEY_VAULT_LOCAL_PATH=secrets  # Path for local mode
```

## Key Management

### Key Generation

- Each file gets a unique 256-bit encryption key
- Keys are generated using a secure random number generator
- Keys are stored in Key Vault with a reference in the database
- Key references follow the format: `file-{file_id}`

### Key Storage

In Azure mode:
- Keys are stored in Azure Key Vault
- Azure managed HSM provides hardware security
- Azure handles key backup and replication

In local mode:
- Keys are stored in a local JSON file
- File is encrypted using system-level file permissions
- Automatic backup creation on updates

### Key Rotation

Keys are automatically rotated:
- After a configurable period (default: 30 days)
- Using lazy rotation to minimize impact
- Old key is kept until rotation is complete
- File is re-encrypted with new key during rotation

## Encryption Process

### File Encryption

1. Generate or retrieve file encryption key
2. Generate random 96-bit IV (nonce)
3. Create AES-256-GCM cipher
4. Write IV to output
5. Encrypt file in chunks
6. Write authentication tag

### File Decryption

1. Read IV from encrypted file
2. Retrieve encryption key from key service
3. Create AES-256-GCM cipher
4. Read authentication tag
5. Decrypt file in chunks
6. Verify authentication tag

## Security Features

1. **Authenticated Encryption**
   - Uses AES-256-GCM mode
   - Provides confidentiality and authenticity
   - Detects tampering with authentication tag

2. **Key Isolation**
   - Each file has a unique key
   - Keys never leave the Key Vault
   - Key references only stored in database

3. **Secure Key Storage**
   - Azure Key Vault in production
   - Local encrypted storage in development
   - Automatic key backup and versioning

4. **Key Rotation**
   - Automatic key rotation
   - Configurable rotation period
   - Transparent to application

5. **Performance Optimization**
   - Streaming encryption for large files
   - Configurable chunk size
   - Key caching with TTL

## Database Schema

The `file_keys` table stores key metadata:

```sql
CREATE TABLE file_keys (
    id SERIAL PRIMARY KEY,
    file_id UUID NOT NULL,
    key_reference TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(file_id, key_reference)
);
```

## Development Mode

For local development:
- Uses file-based key storage
- Keys stored in JSON format
- Automatic backup creation
- Same API as Azure mode

Example local secrets file:
```json
{
  "file-123": {
    "value": "base64-encoded-key",
    "content_type": "application/octet-stream",
    "enabled": true,
    "created_on": "2025-02-27T00:00:00Z",
    "expires_on": "2025-03-27T00:00:00Z"
  }
}
```

## Error Handling

The system includes specialized error types:
- `KeyVaultError`: Key storage/retrieval errors
- `KeyManagementError`: Key management errors
- `EncryptionError`: Encryption/decryption errors

Each error includes:
- Error message
- Operation context
- Timestamp
- Additional details

## Monitoring

The system tracks metrics for:
- Key operations (get/set/delete)
- Key rotation events
- Encryption operations
- File sizes
- Operation latency
- Error counts

Metrics are exposed through Prometheus endpoints.

## Testing

The test suite includes:
- Unit tests for each component
- Integration tests for the complete flow
- Performance tests for large files
- Error handling tests
- Security tests

## Security Considerations

1. **Key Protection**
   - Keys never stored in plaintext
   - Keys never logged or exposed
   - Key access strictly controlled

2. **Data Protection**
   - Authenticated encryption prevents tampering
   - Unique key per file prevents key reuse
   - Automatic key rotation limits key lifetime

3. **Error Handling**
   - No sensitive data in error messages
   - Failed operations properly cleaned up
   - Errors properly logged and monitored

4. **Development Security**
   - Local mode provides secure development
   - Test data never uses production keys
   - Development keys automatically rotated
