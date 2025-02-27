"""File key management service."""

import os
import base64
from uuid import UUID
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    track_encryption_operation,
    track_encryption_error,
    track_encryption_latency,
    track_encryption_file_size
)
from ..types import ErrorContext
from ..utils.exceptions import KeyManagementError
from .base import BaseService
from .keyvault import KeyVaultService
from .database import DatabaseService
from ..config import config

class FileKeyService(BaseService):
    """Service for managing file encryption keys."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize service.
        
        Args:
            settings: Service settings
        """
        super().__init__(settings)
        self.config = config.storage.encryption
        self.key_vault: Optional[KeyVaultService] = None
        self.db: Optional[DatabaseService] = None
        self.key_rotation_interval = timedelta(days=self.config.key_rotation_days)
        self.min_key_length = 32  # 256 bits

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            if not self.config.enabled:
                log_info("Encryption disabled")
                return

            # Get Key Vault service
            from .provider import service_provider
            self.key_vault = service_provider.get(KeyVaultService)
            if not self.key_vault:
                raise KeyManagementError("Key Vault service not available")

            # Get database service
            self.db = service_provider.get(DatabaseService)
            if not self.db:
                raise KeyManagementError("Database service not available")

            # Initialize services if needed
            if not self.key_vault.initialized:
                await self.key_vault.initialize()
            if not self.db.initialized:
                await self.db.initialize()

            # Ensure database table exists
            await self.db.execute("""
                CREATE TABLE IF NOT EXISTS file_keys (
                    id SERIAL PRIMARY KEY,
                    file_id UUID NOT NULL,
                    key_reference TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    UNIQUE(file_id, key_reference)
                )
            """)

            # Create index on file_id
            await self.db.execute("""
                CREATE INDEX IF NOT EXISTS idx_file_keys_file_id 
                ON file_keys(file_id)
            """)

            log_info("File key service initialized", {
                "rotation_interval": f"{self.config.key_rotation_days} days",
                "min_key_length": self.min_key_length,
                "algorithm": self.config.algorithm
            })

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_file_key_service",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize file key service: {str(e)}")
            raise KeyManagementError(
                "Failed to initialize file key service",
                details=error_context
            )

    async def generate_key(self, file_id: UUID) -> bytes:
        """Generate a new encryption key for a file.
        
        Args:
            file_id: File ID to generate key for
            
        Returns:
            Generated key
            
        Raises:
            KeyManagementError: If key generation fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('generate_key')

            # Generate secure random key
            key = os.urandom(self.min_key_length)

            # Store in Key Vault
            key_name = f"file-{str(file_id)}"
            key_b64 = base64.b64encode(key).decode()
            
            await self.key_vault.set_secret(
                name=key_name,
                value=key_b64,
                content_type="application/octet-stream",
                expires_on=datetime.utcnow() + self.key_rotation_interval
            )

            # Store key metadata in database
            async with self.db.transaction():
                await self.db.execute(
                    """
                    INSERT INTO file_keys (
                        file_id,
                        key_reference,
                        created_at,
                        expires_at
                    ) VALUES ($1, $2, $3, $4)
                    """,
                    str(file_id),
                    key_name,
                    datetime.utcnow(),
                    datetime.utcnow() + self.key_rotation_interval
                )

            log_info(f"Generated key for file {file_id}")
            return key

        except Exception as e:
            # Track error
            track_encryption_error('generate_key')

            error_context: ErrorContext = {
                "operation": "generate_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to generate key for file {file_id}: {str(e)}")
            raise KeyManagementError(
                f"Failed to generate key: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'generate_key')

    async def get_key(self, file_id: UUID) -> Optional[bytes]:
        """Get encryption key for a file.
        
        Args:
            file_id: File ID to get key for
            
        Returns:
            Encryption key if found, None otherwise
            
        Raises:
            KeyManagementError: If key retrieval fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('get_key')

            # Get key reference from database
            result = await self.db.fetch_one(
                """
                SELECT key_reference
                FROM file_keys
                WHERE file_id = $1
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                str(file_id)
            )

            if not result:
                return None

            key_name = result['key_reference']

            # Get key from Key Vault
            key_b64 = await self.key_vault.get_secret(key_name)
            if not key_b64:
                return None

            # Decode key
            key = base64.b64decode(key_b64)

            return key

        except Exception as e:
            # Track error
            track_encryption_error('get_key')

            error_context: ErrorContext = {
                "operation": "get_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to get key for file {file_id}: {str(e)}")
            raise KeyManagementError(
                f"Failed to get key: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'get_key')

    async def rotate_key(self, file_id: UUID) -> bytes:
        """Rotate encryption key for a file.
        
        Args:
            file_id: File ID to rotate key for
            
        Returns:
            New encryption key
            
        Raises:
            KeyManagementError: If key rotation fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('rotate_key')

            # Generate new key
            new_key = await self.generate_key(file_id)

            # Mark old keys as expired
            await self.db.execute(
                """
                UPDATE file_keys
                SET expires_at = CURRENT_TIMESTAMP
                WHERE file_id = $1
                AND expires_at > CURRENT_TIMESTAMP
                """,
                str(file_id)
            )

            log_info(f"Rotated key for file {file_id}")
            return new_key

        except Exception as e:
            # Track error
            track_encryption_error('rotate_key')

            error_context: ErrorContext = {
                "operation": "rotate_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to rotate key for file {file_id}: {str(e)}")
            raise KeyManagementError(
                f"Failed to rotate key: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'rotate_key')

    async def cleanup_expired_keys(self) -> None:
        """Clean up expired keys."""
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('cleanup_keys')

            # Get expired key references
            results = await self.db.fetch_all(
                """
                SELECT key_reference
                FROM file_keys
                WHERE expires_at < CURRENT_TIMESTAMP
                """
            )

            # Delete from Key Vault and database
            for result in results:
                key_name = result['key_reference']
                await self.key_vault.delete_secret(key_name)

            await self.db.execute(
                """
                DELETE FROM file_keys
                WHERE expires_at < CURRENT_TIMESTAMP
                """
            )

            log_info(f"Cleaned up {len(results)} expired keys")

        except Exception as e:
            # Track error
            track_encryption_error('cleanup_keys')

            error_context: ErrorContext = {
                "operation": "cleanup_keys",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to clean up expired keys: {str(e)}")
            raise KeyManagementError(
                f"Failed to clean up keys: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'cleanup_keys')

    def derive_key(self, master_key: bytes, salt: bytes, info: bytes) -> bytes:
        """Derive an encryption key from a master key.
        
        Args:
            master_key: Master key to derive from
            salt: Salt for key derivation
            info: Context information for key derivation
            
        Returns:
            Derived key
            
        Raises:
            KeyManagementError: If key derivation fails
        """
        try:
            # Track operation
            track_encryption_operation('derive_key')

            # Create KDF
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )

            # Derive key
            key = kdf.derive(master_key + info)

            return key

        except Exception as e:
            # Track error
            track_encryption_error('derive_key')

            error_context: ErrorContext = {
                "operation": "derive_key",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to derive key: {str(e)}")
            raise KeyManagementError(
                f"Failed to derive key: {str(e)}",
                details=error_context
            )
