"""Common type definitions for the application."""

from typing import (
    TypeVar, Dict, List, Optional, Union, Any, Protocol,
    TypedDict, Callable, Awaitable, Tuple, NewType
)
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from .models.base import Base

# Type variables
ModelType = TypeVar('ModelType', bound=Base)
ResponseType = TypeVar('ResponseType', bound=BaseModel)

# Simple type aliases
JobID = NewType('JobID', str)
UserID = NewType('UserID', str)
FileID = NewType('FileID', str)
TagID = NewType('TagID', str)

# JSON-related types
JSON = Dict[str, Any]
JSONList = List[JSON]
JSONValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]

# Database-related types
DBSession = AsyncSession
QueryResult = List[Dict[str, Any]]
TransactionResult = List[QueryResult]

# Common dictionary types
class FileMetadata(TypedDict):
    """File metadata structure."""
    name: str
    size: int
    type: str
    created_at: datetime
    updated_at: datetime
    owner_id: UserID
    tags: List[TagID]

class JobOptions(TypedDict, total=False):
    """Job options structure."""
    vocabulary: List[str]
    generate_srt: bool
    language: str
    priority: int
    max_retries: int

class JobProgress(TypedDict):
    """Job progress structure."""
    stage: str
    percent: float
    message: Optional[str]

class ZIPProgress(TypedDict):
    """ZIP processing progress structure."""
    stage: str
    percent: float
    files_processed: int
    total_files: int
    current_file: Optional[str]

# Protocol classes
class ServiceProtocol(Protocol):
    """Base protocol for services."""
    initialized: bool
    
    async def initialize(self) -> None:
        """Initialize the service."""
        ...
        
    async def cleanup(self) -> None:
        """Clean up the service."""
        ...

class RepositoryProtocol(Protocol[ModelType]):
    """Base protocol for repositories."""
    session: DBSession
    model_class: type[ModelType]
    
    async def get(self, id: str) -> Optional[ModelType]:
        """Get a record by ID."""
        ...
        
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """List records with optional filtering."""
        ...

# Handler types
RouteHandler = Callable[..., Awaitable[Any]]
ErrorHandler = Callable[..., Awaitable[Any]]
MiddlewareHandler = Callable[..., Awaitable[Any]]

# Metric types
MetricLabels = Dict[str, str]
MetricValue = Union[int, float]
MetricCallback = Callable[[], MetricValue]

# Common result types
class Result(TypedDict):
    """Generic result structure."""
    success: bool
    message: str
    data: Optional[Any]
    error: Optional[str]

class ValidationResult(TypedDict):
    """Validation result structure."""
    valid: bool
    errors: List[str]

class ProcessingResult(TypedDict):
    """Processing result structure."""
    success: bool
    duration: float
    errors: List[str]
    metrics: Dict[str, float]

# Service configuration types
class ServiceConfig(TypedDict, total=False):
    """Service configuration structure."""
    name: str
    enabled: bool
    timeout: int
    retry_count: int
    batch_size: int
    cache_ttl: int
    max_connections: int
    pool_size: int

# Security types
class TokenData(TypedDict):
    """Token data structure."""
    sub: str
    exp: datetime
    scope: List[str]
    roles: List[str]

class Credentials(TypedDict):
    """Credentials structure."""
    username: str
    password: str

# Resource types
class ResourceMetrics(TypedDict):
    """Resource metrics structure."""
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_in: float
    network_out: float

class ResourceLimits(TypedDict):
    """Resource limits structure."""
    max_cpu: float
    max_memory: float
    max_disk: float
    max_bandwidth: float

# Function types
AsyncHandler = Callable[..., Awaitable[Any]]
SyncHandler = Callable[..., Any]
Decorator = Callable[[AsyncHandler], AsyncHandler]

# Error types
class ErrorContext(TypedDict, total=False):
    """Error context structure."""
    operation: str
    resource_id: str
    user_id: str
    timestamp: datetime
    trace_id: str
    details: Dict[str, Any]

# Cache types
CacheKey = Union[str, Tuple[str, ...]]
CacheValue = Any
CacheTTL = int

# Event types
class EventData(TypedDict, total=False):
    """Event data structure."""
    event_type: str
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Dict[str, Any]

# Utility types
class Pagination(TypedDict):
    """Pagination structure."""
    page: int
    per_page: int
    total: int
    pages: int

class TimeRange(TypedDict):
    """Time range structure."""
    start: datetime
    end: datetime
    duration: float
