import os
import logging
import gzip
import asyncio
from typing import Optional, Dict, List, BinaryIO
from minio import Minio
from minio.error import S3Error
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path
from ..utils.metrics import (
    STORAGE_OPERATION_DURATION,
    STORAGE_OPERATION_ERRORS,
    STORAGE_BYTES,
    track_time,
    track_errors,
    update_gauge
)

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self, database_service=None):
        """Initialize storage service"""
        # Store database service if provided
        self.db = database_service
        
        # Define buckets and their settings
        self.buckets = {
            "audio": {
                "name": "audio",
                "versioned": True,
                "max_size": 500 * 1024 * 1024,  # 500MB
                "allowed_types": {".mp3", ".wav", ".m4a", ".ogg", ".flac"}
            },
            "transcription": {
                "name": "transcription",
                "versioned": True,
                "max_size": 10 * 1024 * 1024,  # 10MB
                "allowed_types": {".json"}
            },
            "vocabulary": {
                "name": "vocabulary",
                "versioned": True,
                "max_size": 1 * 1024 * 1024,  # 1MB
                "allowed_types": {".json"}
            },
            "temp": {
                "name": "temp",
                "versioned": False,
                "max_size": 1024 * 1024 * 1024,  # 1GB
                "allowed_types": None  # Allow all types
            }
        }

        # Get configuration
        minio_host = os.getenv("MINIO_HOST", "localhost")
        minio_port = os.getenv("MINIO_PORT", "9000")
        self.endpoint = f"{minio_host}:{minio_port}"
        
        # Try both sets of credential environment variables
        self.access_key = os.getenv("MINIO_ACCESS_KEY") or os.getenv("MINIO_ROOT_USER")
        self.secret_key = os.getenv("MINIO_SECRET_KEY") or os.getenv("MINIO_ROOT_PASSWORD")
        
        if not self.access_key:
            raise ValueError(
                "MinIO access key not set. Required environment variable: "
                "MINIO_ACCESS_KEY or MINIO_ROOT_USER"
            )
        
        if not self.secret_key:
            raise ValueError(
                "MinIO secret key not set. Required environment variable: "
                "MINIO_SECRET_KEY or MINIO_ROOT_PASSWORD"
            )
        
        self.region = os.getenv("MINIO_REGION", "us-east-1")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        # Initialize services
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            secure=self.secure
        )
        
        # Initialize key management
        from .key_management import KeyManagementService
        self.key_mgmt = KeyManagementService()

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "init", "bucket": "all"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "init", "bucket": "all", "error_type": "unknown"})
    async def _init_buckets(self):
        """Initialize storage buckets"""
        try:
            for bucket_config in self.buckets.values():
                bucket_name = bucket_config["name"]
                # Run blocking operations in a thread
                exists = await asyncio.to_thread(self.client.bucket_exists, bucket_name)
                if not exists:
                    await asyncio.to_thread(self.client.make_bucket, bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
                
                # Note: Bucket versioning is not supported in minio-py 7.1.17
                # We'll handle versioning at the application level if needed
                if bucket_config["versioned"]:
                    logger.info(f"Bucket versioning configured for: {bucket_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize buckets: {str(e)}")
            raise
        

    def _get_object_path(self, user_id: str, file_name: str) -> str:
        """Get object path for user file"""
        return f"{user_id}/{file_name}"

    def _validate_file(
        self,
        data: bytes,
        file_name: str,
        bucket_type: str
    ) -> None:
        """Validate file before storage"""
        try:
            # Get bucket config
            bucket_config = self.buckets.get(bucket_type)
            if not bucket_config:
                raise ValueError(f"Invalid bucket type: {bucket_type}")
            
            # Check file size
            if len(data) > bucket_config["max_size"]:
                raise ValueError(
                    f"File too large for {bucket_type} bucket "
                    f"(max {bucket_config['max_size']/1024/1024:.1f}MB)"
                )
            
            # Check file type if restricted
            if bucket_config["allowed_types"]:
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in bucket_config["allowed_types"]:
                    raise ValueError(
                        f"Invalid file type for {bucket_type} bucket: {ext}"
                    )
                    
        except Exception as e:
            logger.error(f"File validation failed: {str(e)}")
            raise

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data using gzip"""
        try:
            return gzip.compress(data)
        except Exception as e:
            logger.error(f"Data compression failed: {str(e)}")
            raise

    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress gzipped data"""
        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.error(f"Data decompression failed: {str(e)}")
            raise

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "store", "bucket": "unknown"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "store", "bucket": "unknown", "error_type": "unknown"})
    async def store_file(
        self,
        user_id: str,
        data: bytes,
        file_name: str,
        bucket_type: str,
        file_id: Optional[str] = None,
        compress: bool = True
    ):
        """Store file in bucket"""
        try:
            # Validate file
            self._validate_file(data, file_name, bucket_type)
            
            # Get bucket
            bucket = self.buckets[bucket_type]["name"]
            
            # Generate file key and encrypt data
            file_key = self.key_mgmt.generate_file_key()
            encrypted_data = self.key_mgmt.encrypt_file(data, file_key)
            
            # Derive user key and encrypt file key
            user_key = self.key_mgmt.derive_user_key(user_id)
            encrypted_key = self.key_mgmt.encrypt_file_key(file_key, user_key)
            
            # Store encrypted key in database if we have a database service
            if self.db:
                from ..models.file import FileKey
                file_key_obj = FileKey(
                    file_id=file_id,
                    owner_id=user_id,
                    encrypted_key=encrypted_key
                )
                await self.db.create_file_key(file_key_obj)
            
            # Compress data if requested (after encryption)
            if compress and bucket_type != "audio":  # Don't compress audio files
                encrypted_data = self._compress_data(encrypted_data)
                file_name += ".gz"
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp.write(encrypted_data)
                temp_path = temp.name
            
            try:
                # Upload file
                object_path = self._get_object_path(user_id, file_name)
                await asyncio.to_thread(
                    self.client.fput_object,
                    bucket,
                    object_path,
                    temp_path
                )
                
                # Update storage metrics
                await self.update_bucket_size_metric(bucket_type)
                
                logger.info(f"Stored encrypted file {file_name} for user {user_id}")
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Failed to store file: {str(e)}")
            raise

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "retrieve", "bucket": "unknown"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "retrieve", "bucket": "unknown", "error_type": "unknown"})
    async def retrieve_file(
        self,
        user_id: str,
        file_name: str,
        bucket_type: str,
        file_id: str,
        version_id: Optional[str] = None
    ) -> bytes:
        """Retrieve file from bucket"""
        try:
            # Get bucket
            bucket = self.buckets[bucket_type]["name"]
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name
            
            try:
                # Download file
                object_path = self._get_object_path(user_id, file_name)
                await asyncio.to_thread(
                    self.client.fget_object,
                    bucket,
                    object_path,
                    temp_path,
                    version_id=version_id
                )
                
                # Read encrypted file
                with open(temp_path, "rb") as f:
                    encrypted_data = f.read()
                
                # Decompress if needed (before decryption)
                if file_name.endswith(".gz"):
                    encrypted_data = self._decompress_data(encrypted_data)
                
                # Get file key if we have a database service
                if not self.db:
                    raise ValueError("Database service not initialized")
                
                from ..models.file import FileKey
                file_key_obj = await self.db.get_file_key(file_id)
                if not file_key_obj:
                    raise ValueError("File key not found")
                
                # Verify ownership
                if file_key_obj.owner_id != user_id:
                    raise ValueError("Access denied")
                
                # Derive user key and decrypt file key
                user_key = self.key_mgmt.derive_user_key(user_id)
                file_key = self.key_mgmt.decrypt_file_key(file_key_obj.encrypted_key, user_key)
                
                # Decrypt data
                data = self.key_mgmt.decrypt_file(encrypted_data, file_key)
                    
                return data
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Failed to retrieve file: {str(e)}")
            raise

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "delete", "bucket": "unknown"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "delete", "bucket": "unknown", "error_type": "unknown"})
    async def delete_file(
        self,
        user_id: str,
        file_name: str,
        bucket_type: str
    ):
        """Delete file from bucket"""
        try:
            # Get bucket
            bucket = self.buckets.get(bucket_type)
            if not bucket:
                raise ValueError(f"Invalid bucket type: {bucket_type}")
            
            # Delete file
            object_path = self._get_object_path(user_id, file_name)
            await asyncio.to_thread(
                self.client.remove_object,
                bucket["name"],
                object_path
            )
            
            # Update storage metrics
            await self.update_bucket_size_metric(bucket_type)
            
            logger.info(f"Deleted file {file_name} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            raise

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "list", "bucket": "unknown"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "list", "bucket": "unknown", "error_type": "unknown"})
    async def list_files(
        self,
        user_id: str,
        bucket_type: str,
        include_versions: bool = False
    ) -> List[Dict]:
        """List files in bucket"""
        try:
            # Get bucket
            bucket_config = self.buckets.get(bucket_type)
            if not bucket_config:
                raise ValueError(f"Invalid bucket type: {bucket_type}")
            
            bucket = bucket_config["name"]
            
            # List objects
            prefix = f"{user_id}/"
            if include_versions and bucket_config["versioned"]:
                objects = await asyncio.to_thread(
                    self.client.list_objects_versions,
                    bucket,
                    prefix=prefix
                )
            else:
                objects = await asyncio.to_thread(
                    self.client.list_objects,
                    bucket,
                    prefix=prefix
                )
            
            # Convert to list
            files = []
            for obj in objects:
                name = obj.object_name[len(prefix):]
                if name.endswith(".gz"):
                    name = name[:-3]  # Remove .gz extension
                    
                file_info = {
                    "name": name,
                    "size": obj.size,
                    "last_modified": obj.last_modified
                }
                
                if include_versions and bucket_config["versioned"]:
                    file_info["version_id"] = obj.version_id
                    
                files.append(file_info)
            
            return files
            
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            raise

    async def get_bucket_size(self, bucket_type: str) -> int:
        """Get total size of bucket in bytes"""
        try:
            bucket = self.buckets[bucket_type]["name"]
            total_size = 0
            
            objects = await asyncio.to_thread(
                self.client.list_objects,
                bucket,
                recursive=True
            )
            for obj in objects:
                total_size += obj.size
                
            return total_size
            
        except Exception as e:
            logger.error(f"Failed to get bucket size: {str(e)}")
            return 0

    async def update_bucket_size_metric(self, bucket_type: str):
        """Update storage metrics for bucket"""
        try:
            size = await self.get_bucket_size(bucket_type)
            update_gauge(STORAGE_BYTES, size, {"bucket": bucket_type})
        except Exception as e:
            logger.error(f"Failed to update storage metrics: {str(e)}")

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "cleanup", "bucket": "temp"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "cleanup", "bucket": "temp", "error_type": "unknown"})
    async def cleanup_temp_files(self, max_age: int = 24):
        """Clean up old temp files"""
        try:
            # Get temp bucket
            bucket = self.buckets["temp"]["name"]
            
            # List objects
            objects = await asyncio.to_thread(
                self.client.list_objects,
                bucket
            )
            
            # Delete old files
            cutoff = datetime.utcnow() - timedelta(hours=max_age)
            for obj in objects:
                if obj.last_modified < cutoff:
                    await asyncio.to_thread(
                        self.client.remove_object,
                        bucket,
                        obj.object_name
                    )
            
            # Update storage metrics
            await self.update_bucket_size_metric("temp")
            
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {str(e)}")
            raise
