# API Documentation

## Authentication

All endpoints require authentication using Azure AD JWT tokens.

### Headers
```
Authorization: Bearer <token>
```

## Endpoints

### Files

#### POST /api/files/upload
Upload a file for transcription.

Request:
```
Content-Type: multipart/form-data

file: File
language: string (optional, default: "de")
vocabulary: string (optional)
```

Response:
```json
{
  "job_id": "uuid",
  "file_name": "string",
  "status": "pending",
  "estimated_time": 300.0,
  "estimated_range": [240.0, 360.0],
  "estimate_confidence": 0.8
}
```

### ZIP Files

#### POST /api/zip/upload
Upload a ZIP file containing multiple audio files for transcription.

Request:
```
Content-Type: multipart/form-data

file: File (ZIP archive)
language: string (optional, default: "de")
```

Response:
```json
[
  {
    "id": "uuid",
    "file_name": "string",
    "status": "pending",
    "estimated_time": 300.0,
    "estimated_range": [240.0, 360.0],
    "estimate_confidence": 0.8,
    "created_at": "2025-02-25T14:30:00Z"
  }
]
```

#### GET /api/zip/progress/{file_id}
Get ZIP extraction progress.

Response:
```json
{
  "file_id": "uuid",
  "progress": 45.5
}
```

#### DELETE /api/zip/{file_id}
Cancel ZIP extraction.

Response:
```json
{
  "file_id": "uuid",
  "status": "cancelled"
}
```

Validation:
- Maximum file size: 1GB
- Maximum files in ZIP: 100
- Allowed file types: .mp3, .wav, .m4a
- No encrypted ZIP files

#### GET /api/files/{file_id}
Get file details and transcription status.

Response:
```json
{
  "id": "uuid",
  "name": "string",
  "size": 1024,
  "created_at": "2025-02-25T14:30:00Z",
  "status": "completed",
  "progress": 100.0,
  "estimated_time": 300.0,
  "estimated_range": [240.0, 360.0],
  "estimate_confidence": 0.8,
  "completed_at": "2025-02-25T14:35:00Z",
  "actual_duration": 295.5
}
```

### Jobs

#### GET /api/jobs
List transcription jobs.

Parameters:
```
status: string (optional) - Filter by status
language: string (optional) - Filter by language
limit: integer (optional, default: 100)
offset: integer (optional, default: 0)
```

Response:
```json
{
  "total": 150,
  "jobs": [
    {
      "id": "uuid",
      "file_name": "string",
      "status": "processing",
      "progress": 45.5,
      "created_at": "2025-02-25T14:30:00Z",
      "estimated_time": 300.0,
      "estimated_range": [240.0, 360.0],
      "estimate_confidence": 0.8,
      "eta": "2025-02-25T14:35:00Z"
    }
  ]
}
```

#### GET /api/jobs/{job_id}
Get job details.

Response:
```json
{
  "id": "uuid",
  "file_name": "string",
  "status": "processing",
  "progress": 45.5,
  "created_at": "2025-02-25T14:30:00Z",
  "updated_at": "2025-02-25T14:32:30Z",
  "estimated_time": 300.0,
  "estimated_range": [240.0, 360.0],
  "estimate_confidence": 0.8,
  "eta": "2025-02-25T14:35:00Z",
  "options": {
    "language": "de",
    "vocabulary": ["word1", "word2"]
  }
}
```

#### DELETE /api/jobs/{job_id}
Cancel a job.

Response:
```json
{
  "id": "uuid",
  "status": "cancelled",
  "cancelled_at": "2025-02-25T14:33:00Z"
}
```

### Time Estimation

#### GET /api/estimate
Get processing time estimate.

Parameters:
```
duration: number (required) - Audio duration in seconds
language: string (required) - Target language code
```

Response:
```json
{
  "estimated_time": 300.0,
  "range": [240.0, 360.0],
  "confidence": 0.8
}
```

#### GET /api/performance
Get performance metrics by language.

Response:
```json
{
  "de": {
    "total_jobs": 100,
    "avg_processing_time": 300.0,
    "min_processing_time": 200.0,
    "max_processing_time": 400.0,
    "avg_word_count": 1000,
    "seconds_per_word": 0.3
  },
  "en": {
    "total_jobs": 50,
    "avg_processing_time": 250.0,
    "min_processing_time": 150.0,
    "max_processing_time": 350.0,
    "avg_word_count": 800,
    "seconds_per_word": 0.25
  }
}
```

### Vocabulary

#### POST /api/vocabulary
Create vocabulary list.

Request:
```json
{
  "name": "string",
  "language": "de",
  "terms": ["word1", "word2"]
}
```

Response:
```json
{
  "id": "uuid",
  "name": "string",
  "language": "de",
  "terms": ["word1", "word2"],
  "created_at": "2025-02-25T14:30:00Z"
}
```

#### GET /api/vocabulary
List vocabulary lists.

Parameters:
```
language: string (optional) - Filter by language
```

Response:
```json
{
  "lists": [
    {
      "id": "uuid",
      "name": "string",
      "language": "de",
      "term_count": 10,
      "created_at": "2025-02-25T14:30:00Z"
    }
  ]
}
```

## Error Responses

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "Invalid request parameters",
  "details": {
    "field": ["error message"]
  }
}
```

### 401 Unauthorized
```json
{
  "error": "unauthorized",
  "message": "Invalid or expired token"
}
```

### 403 Forbidden
```json
{
  "error": "forbidden",
  "message": "Insufficient permissions"
}
```

### 404 Not Found
```json
{
  "error": "not_found",
  "message": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "internal_error",
  "message": "Internal server error"
}
```

## WebSocket Events

### Job Updates
```json
{
  "type": "job_update",
  "job_id": "uuid",
  "status": "processing",
  "progress": 45.5,
  "estimated_time": 300.0,
  "estimated_range": [240.0, 360.0],
  "estimate_confidence": 0.8,
  "eta": "2025-02-25T14:35:00Z"
}
```

### Error Events
```json
{
  "type": "error",
  "error": "processing_error",
  "message": "Error processing file",
  "job_id": "uuid"
}
