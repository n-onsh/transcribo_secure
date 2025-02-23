# API Documentation

## Authentication

All API endpoints (except `/api/v1/auth`) require JWT authentication. Include the JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### Files API

#### POST /api/v1/files/
Upload a file and create a transcription job.

**Request:**
- Method: POST
- Content-Type: multipart/form-data
- Parameters:
  - file: (required) The audio/video file to transcribe
  - vocabulary: (optional) List of custom vocabulary terms
- Headers:
  - Authorization: Bearer <token>

**Response:**
```json
{
  "file": {
    "file_id": "uuid",
    "file_name": "string",
    "file_type": "string",
    "created_at": "datetime"
  },
  "job": {
    "job_id": "uuid",
    "status": "pending",
    "created_at": "datetime"
  }
}
```

#### GET /api/v1/files/{file_id}
Retrieve a file by ID.

**Request:**
- Method: GET
- Parameters:
  - file_id: (path) The ID of the file
- Headers:
  - Authorization: Bearer <token>

**Response:**
```json
{
  "metadata": {
    "file_id": "uuid",
    "file_name": "string",
    "file_type": "string",
    "created_at": "datetime"
  },
  "file_found": true
}
```

### Jobs API

#### GET /api/v1/jobs/{job_id}
Get job status and details.

**Request:**
- Method: GET
- Parameters:
  - job_id: (path) The ID of the job
- Headers:
  - Authorization: Bearer <token>

**Response:**
```json
{
  "job_id": "uuid",
  "status": "string",
  "progress": 0.0,
  "created_at": "datetime",
  "updated_at": "datetime",
  "error": "string"
}
```

#### POST /api/v1/jobs/{job_id}/cancel
Cancel a running job.

**Request:**
- Method: POST
- Parameters:
  - job_id: (path) The ID of the job
- Headers:
  - Authorization: Bearer <token>

**Response:**
```json
{
  "job_id": "uuid",
  "status": "cancelled",
  "updated_at": "datetime"
}
```

### Rate Limiting

The API implements rate limiting per route:
- File operations: 20 requests/minute, burst of 10
- Transcription operations: 10 requests/minute, burst of 5
- Job operations: 50 requests/minute, burst of 20
- Vocabulary operations: 30 requests/minute, burst of 15

When rate limited, the API returns 429 Too Many Requests with a Retry-After header.

### Error Responses

All error responses follow this format:
```json
{
  "code": "ERROR_CODE",
  "message": "Human readable message",
  "details": {
    "field": "Additional error details"
  }
}
```

Common error codes:
- VALIDATION_ERROR: Invalid input data
- AUTHENTICATION_ERROR: Invalid or missing token
- AUTHORIZATION_ERROR: Insufficient permissions
- RESOURCE_NOT_FOUND: Requested resource doesn't exist
- RATE_LIMIT_EXCEEDED: Too many requests
