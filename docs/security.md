# Security Documentation

## Architecture Security

### Service Boundaries
```mermaid
graph TD
    subgraph Docker Network
        subgraph Public
            R[Routes]
            A[Auth Middleware]
        end
        
        subgraph Services
            SP[ServiceProvider]
            DB[DatabaseService]
            KM[KeyManagementService]
            EN[EncryptionService]
            ST[StorageService]
            JM[JobManager]
        end
        
        subgraph Storage
            M[MinIO]
            P[PostgreSQL]
        end
        
        R --> A
        A --> SP
        SP --> DB
        SP --> KM
        SP --> EN
        SP --> ST
        SP --> JM
        
        ST --> M
        DB --> P
    end
```

### Security Layers

1. Network Layer
   - Docker network isolation
   - Container-to-container communication
   - External TLS termination
   - Network segmentation

2. Authentication Layer
   - JWT-based authentication
   - Token validation
   - Role-based access control
   - Secure token storage

3. Service Layer
   - Interface-based design
   - Service validation
   - Dependency injection
   - Error handling

4. Encryption Layer
   - End-to-end encryption
   - Key management
   - File key sharing
   - Secure key storage

5. Storage Layer
   - Encrypted storage
   - Access control
   - Secure file deletion
   - Bucket isolation

## Container Security

### Network Security
```mermaid
graph TD
    subgraph Docker Network
        B[Backend]
        T[Transcriber]
        F[Frontend]
        
        B <--> |Internal Network| T
        F --> |Internal Network| B
    end
    
    subgraph External
        C[Client]
        C --> |HTTPS| F
    end
```

1. Docker Network
   - Isolated network namespace
   - Internal DNS resolution
   - Container-to-container routing
   - Network policy enforcement

2. Communication
   - Internal traffic stays within Docker network
   - No exposure to external networks
   - Service authentication via tokens
   - Request validation

3. External Access
   - TLS termination at edge
   - HTTPS for all external traffic
   - Certificate management
   - CORS configuration

## File Security

### Encryption Process
```mermaid
graph TD
    F[File] --> S[Stream]
    S --> C[Compress]
    C --> E[Encrypt]
    E --> ST[Store]
    
    subgraph Keys
        FK[File Key] --> EK[Encrypt Key]
        UK[User Key] --> EK
        EK --> SK[Store Key]
    end
```

1. File Processing
   - Secure streaming upload:
     * Chunk-by-chunk processing
     * Memory-efficient handling
     * Progress tracking
     * Automatic cleanup
   - File validation:
     * Type checking
     * Size limits
     * Content validation
   - Secure processing:
     * Compression before encryption
     * Unique file key generation
     * End-to-end encryption
     * Secure storage

2. Key Management
   - Generate random file keys
   - Encrypt file keys with user keys
   - Store encrypted keys in database
   - Secure key sharing
   - Azure KeyVault integration (optional):
     * Development fallback to environment variables
     * Automatic migration path to production
     * Secure credential handling

3. Access Control
   - Owner-based access
   - Key-based sharing
   - Permission validation
   - Audit logging

## Job Security

### Job Queue Security
```mermaid
graph TD
    subgraph Queue
        L[Lock] --> C[Claim]
        C --> P[Process]
        P --> U[Update]
    end
    
    subgraph Recovery
        H[Health Check]
        S[Stale Jobs]
        R[Retry]
    end
    
    L --> |FOR UPDATE| J1[Job 1]
    L --> |SKIP LOCKED| J2[Job 2]
    H --> S
    S --> R
```

1. Job Claiming
   - Distributed locking
   - FOR UPDATE SKIP LOCKED
   - Worker validation
   - Timeout handling

2. Job Processing
   - Worker authentication
   - Progress tracking
   - Error handling
   - Automatic recovery

3. Job Recovery
   - Health monitoring
   - Stale job detection
   - Automatic retry
   - Exponential backoff

## Data Protection

### User Data
- Personal data encryption
- Secure data deletion
- Access logging
- Data isolation

### File Data
- End-to-end encryption
- Secure key management
- Access control
- Secure deletion
- Streaming data protection:
  * Chunk validation
  * Progress verification
  * Memory limits
  * Cleanup on failure

### Job Data
- Job isolation
- Progress protection
- Result encryption
- Audit logging

## Monitoring & Auditing

### OpenTelemetry Integration
```mermaid
graph TD
    L[Logs] --> OT[OpenTelemetry]
    M[Metrics] --> OT
    T[Traces] --> OT
    
    OT --> C[Collector]
    C --> LK[Loki]
    C --> PR[Prometheus]
    C --> TP[Tempo]
    
    subgraph Correlation
        TR[Trace ID]
        SP[Span ID]
        AT[Attributes]
    end
```

1. Structured Logging
   - Severity levels
   - Rich context attributes
   - Error details
   - Request correlation

2. Security Metrics
   - Authentication failures
   - Access attempts
   - Job failures
   - Storage usage
   - Upload metrics:
     * Duration
     * Bytes processed
     * Error rates
     * Memory usage

3. Distributed Tracing
   - Request tracking
   - Error correlation
   - Performance monitoring
   - Security event tracking

### Audit Logging
- Access logs with context
- Operation logs with tracing
- Error logs with correlation
- Security events with attributes

### Health Monitoring
- Service health with metrics
- Worker health tracking
- Storage monitoring
- Database health checks

## Configuration Security

### Environment Variables
```bash
# Required
POSTGRES_PASSWORD=<secure_password>
MINIO_ACCESS_KEY=<access_key>
MINIO_SECRET_KEY=<secret_key>

# Azure KeyVault (optional)
AZURE_KEYVAULT_URL=<url>
AZURE_TENANT_ID=<id>
AZURE_CLIENT_ID=<id>
AZURE_CLIENT_SECRET=<secret>

# Optional with secure defaults
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
MINIO_HOST=localhost
MINIO_PORT=9000
```

### Service Configuration
- Secure defaults
- Configuration validation
- Secret management
- Error handling

## Development Security

### Code Security
- Interface-based design
- Type safety
- Error handling
- Input validation
- Memory management:
  * Streaming processing
  * Resource limits
  * Cleanup procedures

### Testing
- Security tests
- Concurrency tests
- Error tests
- Recovery tests
- Streaming tests:
  * Upload validation
  * Progress tracking
  * Memory efficiency
  * Error handling

### Deployment
- Secure builds
- Container security
- Network isolation
- Health monitoring

## Incident Response

### Detection
- Error monitoring with context
- Security alerts with correlation
- Health checks with metrics
- Audit logs with tracing

### Recovery
- Automatic recovery
- Job retry
- Worker failover
- Data protection
- Upload recovery:
  * Chunk validation
  * Progress resumption
  * State recovery
  * Cleanup procedures

### Reporting
- Structured error logging
- Security event correlation
- Audit trail tracking
- Metrics aggregation
