"""Storage service."""

import io
import os
import asyncio
from datetime import datetime
from typing import Dict, Optional, BinaryIO, List, Tuple
from uuid import UUID
from minio import Minio
from minio.error import S3Error
from minio.commonconfig import ENABLED, Filter
from minio.lifecycleconfig import LifecycleConfig, Rule, Expiration
from minio.sseconfig import SseConfig, Rule as SseRule
from minio.versioningconfig import VersioningConfig
from urllib3.exceptions import MaxRetryError
from ..utils.logging import log_info, log_error, log_warning
from ..utils.hash_verification import calculate_data_hash, verify_file_hash, HashVerificationError
from ..utils.metrics import (
    STORAGE_OPERATIONS,
    STORAGE_ERRORS,
    STORAGE_SIZE,
    STORAGE_LATENCY,
    track_storage_operation,
    track_storage_error,
    track_storage_size,
    track_storage_latency
)
from ..utils.exceptions import (
    StorageError,
    StorageAuthenticationError,
    StorageConnectionError,
    StorageOperationError,
    StorageQuotaError,
    StorageFileSizeError,
    StorageFileNotFoundError,
    StorageFileCorruptedError,
    StorageMetadataError,
    ConfigurationError
)
from .base import BaseService
from .encryption import EncryptionService
from .provider import service_provider
from ..config import config

class StorageService(BaseService):
    """Service for managing file storage using MinIO."""

    def __init__(self, settings: Dict):
        """Initialize storage service.
        
        Args:
            settings: Service settings
        """
        super().__init__(settings)
        self.config = config.storage
        self.minio_client: Optional[Minio] = None
        self.encryption_service: Optional[EncryptionService] = None

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize MinIO client
            self.minio_client = Minio(
                endpoint=f"{self.config.endpoint}:{self.config.port}",
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.secure,
                region=self.config.region
            )

            # Configure bucket
            await self._ensure_bucket_exists()

            # Get encryption service
            self.encryption_service = service_provider.get(EncryptionService)
            if not self.encryption_service:
                raise ConfigurationError("Encryption service not available")

            # Initialize encryption service if needed
            if not self.encryption_service.initialized:
                await self.encryption_service.initialize()

            log_info("Storage service initialized", {
                "bucket": self.config.bucket_name,
                "max_file_size": self.config.max_file_size,
                "allowed_extensions": self.config.allowed_extensions,
                "encryption_enabled": self.config.encryption_enabled
            })

        except Exception as e:
            error_context = {
                "operation": "initialize_storage",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize storage service: {str(e)}")
            if isinstance(e, S3Error):
                if 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                else:
                    raise StorageConnectionError(str(e), details=error_context)
            elif isinstance(e, ConfigurationError):
                raise
            else:
                raise StorageError(str(e), details=error_context)

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
        try:
            self.minio_client = None
            log_info("Storage service cleaned up")

        except Exception as e:
            error_context = {
                "operation": "cleanup_storage",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during storage service cleanup: {str(e)}")
            raise StorageOperationError(f"Storage cleanup failed: {str(e)}", details=error_context)

    async def _ensure_bucket_exists(self) -> None:
        """Ensure bucket exists and is properly configured."""
        try:
            # Check if bucket exists
            exists = await asyncio.to_thread(
                self.minio_client.bucket_exists,
                self.config.bucket_name
            )

            if not exists:
                # Create bucket
                await asyncio.to_thread(
                    self.minio_client.make_bucket,
                    self.config.bucket_name
                )

                # Configure bucket
                await self._configure_bucket()

            log_info(f"Bucket {self.config.bucket_name} ready")

        except S3Error as e:
            error_context = {
                "operation": "ensure_bucket",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "bucket": self.config.bucket_name
                }
            }
            log_error(f"MinIO bucket error: {str(e)}")
            if 'AccessDenied' in str(e):
                raise StorageAuthenticationError(str(e), details=error_context)
            else:
                raise StorageConnectionError(str(e), details=error_context)

    async def _configure_bucket(self) -> None:
        """Configure bucket settings."""
        try:
            # Enable versioning
            config = VersioningConfig(ENABLED)
            await asyncio.to_thread(
                self.minio_client.set_bucket_versioning,
                self.config.bucket_name,
                config
            )

            # Configure encryption
            if self.config.encryption_enabled:
                sse_config = SseConfig(
                    [
                        SseRule(
                            ENABLED,
                            sse_algorithm="AES256"
                        )
                    ]
                )
                await asyncio.to_thread(
                    self.minio_client.set_bucket_encryption,
                    self.config.bucket_name,
                    sse_config
                )

            log_info(f"Bucket {self.config.bucket_name} configured")

        except S3Error as e:
            error_context = {
                "operation": "configure_bucket",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "bucket": self.config.bucket_name
                }
            }
            log_error(f"MinIO configuration error: {str(e)}")
            if 'AccessDenied' in str(e):
                raise StorageAuthenticationError(str(e), details=error_context)
            elif 'QuotaExceeded' in str(e):
                raise StorageQuotaError(str(e), details=error_context)
            else:
                raise StorageOperationError(str(e), details=error_context)

    async def store_file(
        self,
        file_id: UUID,
        file: BinaryIO,
        metadata: Optional[Dict] = None,
        encrypt: Optional[bool] = None
    ) -> Dict:
        """Store a file and return its metadata.
        
        Args:
            file_id: File ID
            file: File object
            metadata: Optional metadata
            encrypt: Whether to encrypt the file (defaults to config setting)
            
        Returns:
            File metadata including storage path
            
        Raises:
            StorageError: If storage fails
        """
        start_time = datetime.utcnow()
        try:
            # Track operation
            track_storage_operation('store')

            # Use configuration default if encrypt not specified
            if encrypt is None:
                encrypt = self.config.encryption_enabled

            # Prepare metadata
            meta = metadata or {}
            meta.update({
                'file_id': str(file_id),
                'created_at': datetime.utcnow().isoformat(),
                'encrypted': str(encrypt).lower()
            })

            # Create temporary buffer
            temp_buffer = io.BytesIO()

            # Encrypt if needed
            if encrypt:
                await self.encryption_service.encrypt_file(
                    file_id=file_id,
                    input_file=file,
                    output_file=temp_buffer
                )
                temp_buffer.seek(0)
                data = temp_buffer.read()
            else:
                data = file.read()

            # Calculate hash
            file_hash = calculate_data_hash(data)
            meta['hash'] = file_hash
            meta['hash_algorithm'] = 'sha256'

            # Store in MinIO
            object_name = f"files/{file_id}"
            data_size = len(data)
            data_stream = io.BytesIO(data)

            await asyncio.to_thread(
                self.minio_client.put_object,
                self.config.bucket_name,
                object_name,
                data_stream,
                data_size,
                metadata=meta
            )

            # Track metrics
            track_storage_size(data_size)

            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_storage_latency(duration)

            log_info(f"Stored file {file_id} ({data_size} bytes)")

            return {
                'file_id': str(file_id),
                'path': f"minio://{self.config.bucket_name}/{object_name}",
                'size': data_size,
                'hash': file_hash,
                'hash_algorithm': 'sha256',
                'encrypted': encrypt,
                'metadata': meta
            }

        except Exception as e:
            track_storage_error()
            error_context = {
                "operation": "store_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to store file {file_id}: {str(e)}")
            if isinstance(e, S3Error):
                if 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                elif 'QuotaExceeded' in str(e):
                    raise StorageQuotaError(str(e), details=error_context)
                elif 'EntityTooLarge' in str(e):
                    raise StorageFileSizeError(str(e), details=error_context)
                else:
                    raise StorageOperationError(str(e), details=error_context)
            elif isinstance(e, HashVerificationError):
                raise StorageFileCorruptedError(str(e), details=error_context)
            else:
                raise StorageError(str(e), details=error_context)

    async def get_file(
        self,
        file_id: UUID,
        decrypt: Optional[bool] = None
    ) -> Tuple[BinaryIO, Dict]:
        """Get a file and its metadata.
        
        Args:
            file_id: File ID
            decrypt: Whether to decrypt the file (defaults to True if encrypted)
            
        Returns:
            Tuple of (file object, metadata)
            
        Raises:
            StorageError: If retrieval fails
        """
        start_time = datetime.utcnow()
        try:
            # Track operation
            track_storage_operation('get')

            # Get object
            object_name = f"files/{file_id}"
            try:
                response = await asyncio.to_thread(
                    self.minio_client.get_object,
                    self.config.bucket_name,
                    object_name
                )
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    return None, {}
                raise

            # Get metadata
            metadata = response.metadata or {}
            encrypted = metadata.get('encrypted', 'false').lower() == 'true'

            # Read data
            data = await asyncio.to_thread(response.read)
            data_stream = io.BytesIO(data)

            # Verify hash if present
            if 'hash' in metadata:
                file_hash = calculate_data_hash(data)
                if file_hash != metadata['hash']:
                    raise HashVerificationError("File hash verification failed")

            # Decrypt if needed
            if encrypted and (decrypt is None or decrypt):
                decrypted_buffer = io.BytesIO()
                data_stream.seek(0)
                await self.encryption_service.decrypt_file(
                    file_id=file_id,
                    input_file=data_stream,
                    output_file=decrypted_buffer
                )
                decrypted_buffer.seek(0)
                result = decrypted_buffer
            else:
                data_stream.seek(0)
                result = data_stream

            # Track metrics
            track_storage_size(len(data))

            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_storage_latency(duration)

            log_info(f"Retrieved file {file_id}")

            return result, metadata

        except Exception as e:
            track_storage_error()
            error_context = {
                "operation": "get_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to get file {file_id}: {str(e)}")
            if isinstance(e, S3Error):
                if e.code == 'NoSuchKey':
                    raise StorageFileNotFoundError(str(e), details=error_context)
                elif 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                else:
                    raise StorageOperationError(str(e), details=error_context)
            elif isinstance(e, HashVerificationError):
                raise StorageFileCorruptedError(str(e), details=error_context)
            else:
                raise StorageError(str(e), details=error_context)

    async def delete_file(self, file_id: UUID) -> bool:
        """Delete a file.
        
        Args:
            file_id: File ID
            
        Returns:
            True if file was deleted, False if not found
            
        Raises:
            StorageError: If deletion fails
        """
        try:
            # Track operation
            track_storage_operation('delete')

            # Get object info first
            object_name = f"files/{file_id}"
            try:
                stat = await asyncio.to_thread(
                    self.minio_client.stat_object,
                    self.config.bucket_name,
                    object_name
                )
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    return False
                raise

            # Delete object
            await asyncio.to_thread(
                self.minio_client.remove_object,
                self.config.bucket_name,
                object_name
            )

            # Track metrics
            if stat.size:
                track_storage_size(-stat.size)

            log_info(f"Deleted file {file_id}")
            return True

        except Exception as e:
            track_storage_error()
            error_context = {
                "operation": "delete_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to delete file {file_id}: {str(e)}")
            if isinstance(e, S3Error):
                if e.code == 'NoSuchKey':
                    raise StorageFileNotFoundError(str(e), details=error_context)
                elif 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                else:
                    raise StorageOperationError(str(e), details=error_context)
            else:
                raise StorageError(str(e), details=error_context)

    async def get_file_info(self, file_id: UUID) -> Optional[Dict]:
        """Get file information.
        
        Args:
            file_id: File ID
            
        Returns:
            File metadata if found, None otherwise
            
        Raises:
            StorageError: If retrieval fails
        """
        try:
            # Track operation
            track_storage_operation('info')

            # Get object info
            object_name = f"files/{file_id}"
            try:
                stat = await asyncio.to_thread(
                    self.minio_client.stat_object,
                    self.config.bucket_name,
                    object_name
                )
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    return None
                raise

            metadata = stat.metadata or {}
            return {
                'file_id': str(file_id),
                'path': f"minio://{self.config.bucket_name}/{object_name}",
                'size': stat.size,
                'hash': metadata.get('hash'),
                'hash_algorithm': metadata.get('hash_algorithm'),
                'encrypted': metadata.get('encrypted', 'false').lower() == 'true',
                'created_at': metadata.get('created_at'),
                'metadata': metadata
            }

        except Exception as e:
            track_storage_error()
            error_context = {
                "operation": "get_file_info",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to get info for file {file_id}: {str(e)}")
            if isinstance(e, S3Error):
                if e.code == 'NoSuchKey':
                    raise StorageFileNotFoundError(str(e), details=error_context)
                elif 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                else:
                    raise StorageOperationError(str(e), details=error_context)
            else:
                raise StorageMetadataError(str(e), details=error_context)

    async def get_file_size(self, file_id: UUID) -> Optional[int]:
        """Get file size.
        
        Args:
            file_id: File ID
            
        Returns:
            File size in bytes if found, None otherwise
            
        Raises:
            StorageError: If retrieval fails
        """
        try:
            # Track operation
            track_storage_operation('size')

            # Get object info
            object_name = f"files/{file_id}"
            try:
                stat = await asyncio.to_thread(
                    self.minio_client.stat_object,
                    self.config.bucket_name,
                    object_name
                )
                return stat.size
            except S3Error as e:
                if e.code == 'NoSuchKey':
                    return None
                raise

        except Exception as e:
            track_storage_error()
            error_context = {
                "operation": "get_file_size",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to get size for file {file_id}: {str(e)}")
            if isinstance(e, S3Error):
                if e.code == 'NoSuchKey':
                    raise StorageFileNotFoundError(str(e), details=error_context)
                elif 'AccessDenied' in str(e):
                    raise StorageAuthenticationError(str(e), details=error_context)
                else:
                    raise StorageOperationError(str(e), details=error_context)
            else:
                raise StorageMetadataError(str(e), details=error_context)
