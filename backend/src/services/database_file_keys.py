"""Database file keys service."""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import TranscriboError
from .base import BaseService
from .database import DatabaseService
from ..utils.metrics import (
    KEY_OPERATIONS,
    KEY_ERRORS,
    KEY_LATENCY,
    track_key_operation,
    track_key_error,
    track_key_latency
)

class DatabaseFileKeyService(BaseService):
    """Service for managing file keys in the database."""

    def __init__(self, settings: Dict[str, Any], database_service: Optional[DatabaseService] = None):
        """Initialize database file key service.
        
        Args:
            settings: Service settings
            database_service: Optional database service instance
        """
        super().__init__(settings)
        self.db = database_service

    async def _initialize_impl(self):
        """Initialize the service implementation."""
        try:
            # Initialize database settings
            self.table_name = self.settings.get('file_keys_table', 'file_keys')
            self.key_ttl = int(self.settings.get('file_key_ttl', 86400))  # 24 hours

            # Initialize database connection
            self.db = await self._init_database()

        except Exception as e:
            log_error(f"Failed to initialize database file key service: {str(e)}")
            raise TranscriboError(
                "Failed to initialize database file key service",
                details={"error": str(e)}
            )

    async def _cleanup_impl(self):
        """Clean up service implementation."""
        try:
            if self.db:
                await self.db.cleanup()

        except Exception as e:
            log_error(f"Error during database file key service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up database file key service",
                details={"error": str(e)}
            )

    async def store_key(self, file_id: str, key_data: Dict) -> bool:
        """Store a file key in the database.
        
        Args:
            file_id: File ID
            key_data: Key data to store
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            TranscriboError: If operation fails
        """
        return await self._execute_operation(
            'store_key',
            self._store_key,
            file_id,
            key_data
        )

    async def get_key(self, file_id: str) -> Optional[Dict]:
        """Get a file key from the database.
        
        Args:
            file_id: File ID
            
        Returns:
            Key data if found, None otherwise
            
        Raises:
            TranscriboError: If operation fails
        """
        return await self._execute_operation(
            'get_key',
            self._get_key,
            file_id
        )

    async def delete_key(self, file_id: str) -> bool:
        """Delete a file key from the database.
        
        Args:
            file_id: File ID
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            TranscriboError: If operation fails
        """
        return await self._execute_operation(
            'delete_key',
            self._delete_key,
            file_id
        )

    async def list_keys(self, filter_params: Optional[Dict] = None) -> List[Dict]:
        """List file keys from the database.
        
        Args:
            filter_params: Optional filter parameters
            
        Returns:
            List of key data
            
        Raises:
            TranscriboError: If operation fails
        """
        return await self._execute_operation(
            'list_keys',
            self._list_keys,
            filter_params
        )

    async def _init_database(self) -> DatabaseService:
        """Initialize database connection."""
        if not self.db:
            self.db = DatabaseService(self.settings)
            await self.db.initialize()
            
            # Create table if not exists
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                file_id TEXT PRIMARY KEY,
                key_data JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP WITH TIME ZONE,
                metadata JSONB
            )
            """
            
            try:
                await self.db.execute_query(create_table_query)
                log_info(f"Created {self.table_name} table if not exists")
            except Exception as e:
                log_error(f"Failed to create {self.table_name} table: {str(e)}")
                raise TranscriboError(
                    f"Failed to create {self.table_name} table",
                    details={"error": str(e)}
                )
        
        return self.db

    async def _store_key(self, file_id: str, key_data: Dict) -> bool:
        """Store key in database."""
        self._check_initialized()
            
        try:
            # Calculate expiration time
            expires_at = datetime.utcnow() + timedelta(seconds=self.key_ttl)
            
            # Insert or update key
            query = f"""
            INSERT INTO {self.table_name} (file_id, key_data, expires_at)
            VALUES ($id, $key_data, $expires_at)
            ON CONFLICT (file_id) DO UPDATE
            SET key_data = $key_data,
                expires_at = $expires_at,
                created_at = CURRENT_TIMESTAMP
            """
            
            await self.db.execute_query(
                query,
                {
                    'id': file_id,
                    'key_data': key_data,
                    'expires_at': expires_at.isoformat()
                }
            )
            
            return True
            
        except Exception as e:
            log_error(f"Failed to store key for file {file_id}: {str(e)}")
            return False

    async def _get_key(self, file_id: str) -> Optional[Dict]:
        """Get key from database."""
        self._check_initialized()
            
        try:
            # Get key if not expired
            query = f"""
            SELECT key_data, created_at, expires_at, metadata
            FROM {self.table_name}
            WHERE file_id = $id
            AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """
            
            results = await self.db.execute_query(query, {'id': file_id})
            
            if results and len(results) > 0:
                return {
                    'key_data': results[0]['key_data'],
                    'created_at': results[0]['created_at'],
                    'expires_at': results[0]['expires_at'],
                    'metadata': results[0]['metadata']
                }
            
            return None
            
        except Exception as e:
            log_error(f"Failed to get key for file {file_id}: {str(e)}")
            return None

    async def _delete_key(self, file_id: str) -> bool:
        """Delete key from database."""
        self._check_initialized()
            
        try:
            query = f"""
            DELETE FROM {self.table_name}
            WHERE file_id = $id
            """
            
            result = await self.db.execute_query(query, {'id': file_id})
            return len(result) > 0
            
        except Exception as e:
            log_error(f"Failed to delete key for file {file_id}: {str(e)}")
            return False

    async def _list_keys(self, filter_params: Optional[Dict] = None) -> List[Dict]:
        """List keys from database."""
        self._check_initialized()
            
        try:
            # Build query based on filters
            query = f"""
            SELECT file_id, key_data, created_at, expires_at, metadata
            FROM {self.table_name}
            WHERE (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """
            
            params = {}
            
            if filter_params:
                if 'created_after' in filter_params:
                    query += " AND created_at > $created_after"
                    params['created_after'] = filter_params['created_after']
                    
                if 'created_before' in filter_params:
                    query += " AND created_at < $created_before"
                    params['created_before'] = filter_params['created_before']
            
            query += " ORDER BY created_at DESC"
            
            results = await self.db.execute_query(query, params)
            
            return [{
                'file_id': row['file_id'],
                'key_data': row['key_data'],
                'created_at': row['created_at'],
                'expires_at': row['expires_at'],
                'metadata': row['metadata']
            } for row in results]
            
        except Exception as e:
            log_error(f"Failed to list keys: {str(e)}")
            return []

    async def _execute_operation(self, operation: str, func: callable, *args, **kwargs):
        """Execute a database operation with metrics tracking.
        
        Args:
            operation: Operation name for metrics
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Operation result
            
        Raises:
            TranscriboError: If operation fails
        """
        start_time = logging.time()
        try:
            # Track operation
            KEY_OPERATIONS.labels(operation=operation).inc()
            track_key_operation(operation)

            # Execute operation
            result = await func(*args, **kwargs)
            
            # Track latency
            duration = logging.time() - start_time
            KEY_LATENCY.observe(duration)
            track_key_latency(duration)
            
            return result

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            raise TranscriboError(
                f"Failed to {operation}",
                details={"error": str(e)}
            )
