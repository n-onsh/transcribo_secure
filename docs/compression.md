# Compression & Encryption

This document outlines the compression and encryption implementation in the Transcribo Secure system.

## Overview

Files are processed in the following order:
1. Compression (before encryption)
2. Encryption (after compression)
3. Storage (encrypted form)
4. Decryption (on access)
5. Decompression (after decryption)

## Compression

### Implementation

```python
# backend/src/services/storage.py
async def compress_file(data: bytes) -> bytes:
    """Compress file data using gzip"""
    return gzip.compress(data, compresslevel=6)

async def decompress_file(data: bytes) -> bytes:
    """Decompress gzipped file data"""
    return gzip.decompress(data)
```

### Configuration
```python
# backend/src/config.py
COMPRESSION_LEVEL = 6  # Balance between speed and size
COMPRESSION_THRESHOLD = 1024  # Minimum size for compression
COMPRESSION_TYPES = {
    'audio/mpeg': True,
    'audio/wav': True,
    'audio/x-wav': True,
    'audio/x-m4a': True,
    'application/zip': False  # Already compressed
}
```

### Process Flow
1. Check file size and type
2. Apply compression if beneficial
3. Track compression ratio
4. Handle streaming compression
5. Monitor performance

## Encryption

### Key Management
```python
# backend/src/services/key_management.py
async def generate_file_key() -> bytes:
    """Generate new AES-256 key"""
    return os.urandom(32)

async def wrap_key(key: bytes, kek: bytes) -> bytes:
    """Wrap file key with key encryption key"""
    wrapper = Fernet(kek)
    return wrapper.encrypt(key)
```

### Implementation
```python
# backend/src/services/encryption.py
async def encrypt_file(data: bytes, key: bytes) -> bytes:
    """Encrypt file data using AES-256-GCM"""
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(data)
    return nonce + tag + ciphertext

async def decrypt_file(data: bytes, key: bytes) -> bytes:
    """Decrypt file data using AES-256-GCM"""
    nonce = data[:12]
    tag = data[12:28]
    ciphertext = data[28:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)
```

### Key Storage
```python
# backend/src/models/file_key.py
class FileKey(BaseModel):
    id: UUID
    owner_id: UUID
    wrapped_key: bytes
    created_at: datetime
    updated_at: datetime
```

## Streaming Implementation

### Upload Flow
```python
# backend/src/services/storage.py
async def stream_upload(
    file: UploadFile,
    key: bytes,
    chunk_size: int = 8192
) -> str:
    """Stream file upload with compression and encryption"""
    # Initialize compression
    compressor = zlib.compressobj(level=6)
    
    # Initialize encryption
    nonce = os.urandom(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    
    # Stream to storage
    object_id = str(uuid.uuid4())
    async with storage.writer(object_id) as writer:
        # Write nonce
        await writer.write(nonce)
        
        # Process chunks
        while chunk := await file.read(chunk_size):
            # Compress
            compressed = compressor.compress(chunk)
            if compressed:
                # Encrypt
                encrypted = cipher.encrypt(compressed)
                await writer.write(encrypted)
        
        # Finish compression
        compressed = compressor.flush()
        if compressed:
            # Encrypt final chunk
            encrypted = cipher.encrypt(compressed)
            await writer.write(encrypted)
        
        # Write tag
        await writer.write(cipher.digest())
    
    return object_id
```

### Download Flow
```python
# backend/src/services/storage.py
async def stream_download(
    object_id: str,
    key: bytes,
    chunk_size: int = 8192
) -> AsyncGenerator[bytes, None]:
    """Stream file download with decryption and decompression"""
    # Initialize decompression
    decompressor = zlib.decompressobj()
    
    async with storage.reader(object_id) as reader:
        # Read nonce
        nonce = await reader.read(12)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        
        # Process chunks
        while chunk := await reader.read(chunk_size):
            # Decrypt
            decrypted = cipher.decrypt(chunk)
            
            # Decompress
            decompressed = decompressor.decompress(decrypted)
            if decompressed:
                yield decompressed
        
        # Verify tag
        tag = await reader.read(16)
        cipher.verify(tag)
        
        # Finish decompression
        final = decompressor.flush()
        if final:
            yield final
```

## Performance Considerations

### Compression
1. File Type Analysis
   - Check if compression beneficial
   - Monitor compression ratios
   - Track processing time
   - Adjust parameters

2. Resource Usage
   - CPU utilization
   - Memory consumption
   - Disk I/O
   - Network bandwidth

3. Optimization
   - Chunk size tuning
   - Compression level
   - Buffer management
   - Parallel processing

### Encryption
1. Key Management
   - Key generation
   - Key rotation
   - Key storage
   - Access control

2. Performance
   - Algorithm selection
   - Mode of operation
   - Chunk size
   - Buffer handling

3. Security
   - Key protection
   - Nonce management
   - Tag validation
   - Error handling

## Monitoring

### Metrics
```python
# backend/src/utils/metrics.py
COMPRESSION_RATIO = Histogram(
    "file_compression_ratio",
    "File compression ratio",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
)

ENCRYPTION_TIME = Histogram(
    "file_encryption_seconds",
    "File encryption time in seconds",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)
```

### Logging
```python
# backend/src/utils/logging.py
logger.info(
    "File processed",
    extra={
        "file_id": file_id,
        "original_size": size,
        "compressed_size": compressed_size,
        "compression_ratio": ratio,
        "processing_time": duration
    }
)
```

## Error Handling

### Compression Errors
```python
# backend/src/utils/exceptions.py
class CompressionError(Exception):
    """Base class for compression errors"""
    pass

class DecompressionError(Exception):
    """Base class for decompression errors"""
    pass
```

### Encryption Errors
```python
# backend/src/utils/exceptions.py
class EncryptionError(Exception):
    """Base class for encryption errors"""
    pass

class DecryptionError(Exception):
    """Base class for decryption errors"""
    pass
```

## Testing

### Unit Tests
```python
# tests/unit/test_compression.py
async def test_compression_ratio():
    data = b"test" * 1000
    compressed = await compress_file(data)
    ratio = len(compressed) / len(data)
    assert ratio < 0.5

# tests/unit/test_encryption.py
async def test_encryption_decryption():
    key = await generate_file_key()
    data = b"test data"
    encrypted = await encrypt_file(data, key)
    decrypted = await decrypt_file(encrypted, key)
    assert data == decrypted
```

### Integration Tests
```python
# tests/integration/test_storage.py
async def test_file_upload_download():
    # Test complete flow
    file_id = await upload_file(test_file)
    downloaded = await download_file(file_id)
    assert test_file.read() == downloaded
```

## Security Notes

### Key Protection
1. Key Generation
   - Use cryptographically secure RNG
   - Proper key length
   - Key format validation
   - Key storage security

2. Key Management
   - Regular rotation
   - Access control
   - Audit logging
   - Backup procedures

### Data Protection
1. In Transit
   - TLS encryption
   - Certificate validation
   - Protocol security
   - Network security

2. At Rest
   - Encryption at rest
   - Access control
   - Storage security
   - Backup encryption

## Maintenance

### Regular Tasks
1. Key Rotation
   - Schedule rotation
   - Validate new keys
   - Update references
   - Archive old keys

2. Performance Monitoring
   - Check ratios
   - Monitor times
   - Track errors
   - Analyze metrics

### Cleanup
1. Temporary Files
   - Remove temp files
   - Clean buffers
   - Free resources
   - Log cleanup

2. Old Data
   - Archive policy
   - Secure deletion
   - Key cleanup
   - Log retention
