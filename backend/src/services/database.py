"""Database service."""

import logging
import asyncpg
from typing import Dict, Optional, List, Any, Type, TypeVar
from uuid import UUID
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import DatabaseError, TranscriboError
from ..utils.metrics import (
    DB_OPERATIONS,
    DB_ERRORS,
    DB_LATENCY,
    DB_CONNECTIONS,
    track_db_operation,
    track_db_error,
    track_db_latency,
    track_db_connection
)
from .base import BaseService
from .repository import BaseRepository
from ..models.base import Base

T = TypeVar('T', bound=Base)

class DatabaseService(BaseService):
    """Service for database operations."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize database service."""
        super().__init__(settings)
        self.pool = None
        self.repositories: Dict[Type[Base], BaseRepository] = {}

    async def _initialize_impl(self):
        """Initialize database connection."""
        try:
            # Initialize database settings
            self.database_url = self.settings.get('database_url')
            self.min_connections = int(self.settings.get('min_db_connections', 1))
            self.max_connections = int(self.settings.get('max_db_connections', 10))

            if not self.database_url:
                raise ValueError("Database URL not configured")

            # Initialize connection pool
            self.pool = await self._create_pool()
            
            # Track initial connections
            DB_CONNECTIONS.set(self.min_connections)
            track_db_connection(self.min_connections)

        except Exception as e:
            log_error(f"Failed to initialize database service: {str(e)}")
            raise TranscriboError(
                "Failed to initialize database service",
                details={"error": str(e)}
            )

    async def _cleanup_impl(self):
        """Clean up database connections."""
        try:
            if self.pool:
                await self.pool.close()
            self.repositories.clear()

        except Exception as e:
            log_error(f"Error during database service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up database service",
                details={"error": str(e)}
            )

    def get_repository(self, model_class: Type[T]) -> BaseRepository[T]:
        """Get a repository for a model class.
        
        Args:
            model_class: SQLAlchemy model class
            
        Returns:
            Repository instance for the model class
        """
        if model_class not in self.repositories:
            self.repositories[model_class] = BaseRepository(self.pool, model_class)
        return self.repositories[model_class]

    async def execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a database query."""
        start_time = logging.time()
        try:
            # Track operation
            DB_OPERATIONS.labels(operation='query').inc()
            track_db_operation('query')

            # Execute query
            result = await self._execute_query(query, params)
            
            # Track latency
            duration = logging.time() - start_time
            DB_LATENCY.observe(duration)
            track_db_latency(duration)
            
            log_info(f"Executed query: {query[:100]}...")
            return result

        except Exception as e:
            DB_ERRORS.inc()
            track_db_error()
            log_error(f"Error executing query: {str(e)}")
            raise TranscriboError(
                "Failed to execute query",
                details={"error": str(e)}
            )

    async def execute_transaction(self, queries: List[Dict]) -> List[Dict]:
        """Execute a database transaction."""
        start_time = logging.time()
        try:
            # Track operation
            DB_OPERATIONS.labels(operation='transaction').inc()
            track_db_operation('transaction')

            # Execute transaction
            results = await self._execute_transaction(queries)
            
            # Track latency
            duration = logging.time() - start_time
            DB_LATENCY.observe(duration)
            track_db_latency(duration)
            
            log_info(f"Executed transaction with {len(queries)} queries")
            return results

        except Exception as e:
            DB_ERRORS.inc()
            track_db_error()
            log_error(f"Error executing transaction: {str(e)}")
            raise TranscriboError(
                "Failed to execute transaction",
                details={"error": str(e)}
            )

    async def get_connection_stats(self) -> Dict:
        """Get database connection statistics."""
        try:
            # Get stats
            stats = await self._get_pool_stats()
            
            # Track current connections
            current_connections = stats.get('active_connections', 0)
            DB_CONNECTIONS.set(current_connections)
            track_db_connection(current_connections)
            
            log_info("Retrieved database connection stats", extra=stats)
            return stats

        except Exception as e:
            log_error(f"Error getting connection stats: {str(e)}")
            raise TranscriboError(
                "Failed to get connection stats",
                details={"error": str(e)}
            )

    async def _create_pool(self):
        """Create database connection pool."""
        try:
            # Create connection pool
            pool = await asyncpg.create_pool(
                dsn=self.database_url,
                min_size=self.min_connections,
                max_size=self.max_connections,
                command_timeout=60.0,
                # Setup row factory to return dictionaries
                init=lambda conn: conn.set_type_codec(
                    'json',
                    encoder=str,
                    decoder=str,
                    schema='pg_catalog'
                )
            )
            
            if not pool:
                raise DatabaseError("Failed to create connection pool")
            
            log_info("Created database connection pool", extra={
                'min_connections': self.min_connections,
                'max_connections': self.max_connections
            })
            
            return pool
            
        except asyncpg.PostgresError as e:
            log_error(f"PostgreSQL error creating pool: {str(e)}")
            raise TranscriboError(
                "Failed to create connection pool",
                details={"error": str(e)}
            )
        except Exception as e:
            log_error(f"Unexpected error creating pool: {str(e)}")
            raise TranscriboError(
                "Failed to create connection pool",
                details={"error": str(e)}
            )

    async def _execute_query(self, query: str, params: Optional[Dict] = None) -> List[Dict]:
        """Execute a single query."""
        self._check_initialized()
            
        try:
            async with self.pool.acquire() as connection:
                # Convert dict params to list for asyncpg
                param_values = []
                if params:
                    # Replace $name with $1, $2, etc. and build param list
                    for i, (name, value) in enumerate(params.items(), 1):
                        query = query.replace(f"${name}", f"${i}")
                        param_values.append(value)
                
                # Execute query
                result = await connection.fetch(query, *param_values)
                
                # Convert records to dicts
                return [dict(record) for record in result]
                
        except asyncpg.PostgresError as e:
            log_error(f"PostgreSQL error executing query: {str(e)}")
            raise TranscriboError(
                "Query execution failed",
                details={"error": str(e)}
            )
        except Exception as e:
            log_error(f"Unexpected error executing query: {str(e)}")
            raise TranscriboError(
                "Query execution failed",
                details={"error": str(e)}
            )

    async def _execute_transaction(self, queries: List[Dict]) -> List[Dict]:
        """Execute multiple queries in a transaction."""
        self._check_initialized()
            
        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    results = []
                    
                    for query_info in queries:
                        query = query_info['query']
                        params = query_info.get('params', {})
                        
                        # Convert dict params to list
                        param_values = []
                        if params:
                            for i, (name, value) in enumerate(params.items(), 1):
                                query = query.replace(f"${name}", f"${i}")
                                param_values.append(value)
                        
                        # Execute query
                        result = await connection.fetch(query, *param_values)
                        results.append([dict(record) for record in result])
                    
                    return results
                    
        except asyncpg.PostgresError as e:
            log_error(f"PostgreSQL error executing transaction: {str(e)}")
            raise TranscriboError(
                "Transaction failed",
                details={"error": str(e)}
            )
        except Exception as e:
            log_error(f"Unexpected error executing transaction: {str(e)}")
            raise TranscriboError(
                "Transaction failed",
                details={"error": str(e)}
            )

    async def _get_pool_stats(self) -> Dict:
        """Get connection pool statistics."""
        self._check_initialized()
            
        try:
            return {
                'active_connections': len(self.pool._holders),  # Currently acquired connections
                'idle_connections': len(self.pool._queue._queue),  # Available connections
                'max_connections': self.max_connections,
                'min_connections': self.min_connections,
                'closed': self.pool._closed
            }
        except Exception as e:
            log_error(f"Error getting pool stats: {str(e)}")
            raise TranscriboError(
                "Failed to get pool stats",
                details={"error": str(e)}
            )
