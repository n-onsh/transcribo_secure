"""Application constants."""

# API versioning
API_V1_PREFIX = "/api/v1"

# Error codes
ERROR_CODES = {
    "VALIDATION_ERROR": "ERR_400",
    "AUTHENTICATION_ERROR": "ERR_401",
    "AUTHORIZATION_ERROR": "ERR_403",
    "NOT_FOUND_ERROR": "ERR_404",
    "CONFLICT_ERROR": "ERR_409",
    "INTERNAL_ERROR": "ERR_500"
}

# Pagination defaults
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 1000

# Request ID header
REQUEST_ID_HEADER = "X-Request-ID"
