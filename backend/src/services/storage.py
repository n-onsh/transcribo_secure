import os
import gzip
import asyncio
import io
from typing import Optional, Dict, List, BinaryIO, Callable
from minio import Minio
from minio.error import S3Error
from datetime import datetime, timedelta
import tempfile
import magic
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from ..models.file_key import FileKeyCreate
from ..services.interfaces import (
    StorageInterface,
    DatabaseInterface,
    KeyManagementInterface,
    EncryptionInterface
)
from ..utils.metrics import (
    STORAGE_OPERATION_DURATION,
    STORAGE_OPERATION_ERRORS,
    STORAGE_BYTES,
    track_time,
    track_errors,
    update_gauge
)

logger = logs.get_logger(__name__)

class StorageService(StorageInterface):
    def __init__(
        self,
        database_service: Optional[DatabaseInterface] = None,
        key_management_service: Optional[KeyManagementInterface] = None,
        encryption_service: Optional[EncryptionInterface] = None
    ):
        """Initialize storage service"""
        # Store services
        self.db = database_service
        self.key_mgmt = key_management_service
        self.encryption = encryption_service
        
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
        
        # Initialize MinIO client
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            secure=self.secure
        )

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
                    logger.emit(
                        f"Created bucket: {bucket_name}",
                        severity=Severity.INFO
                    )
                
                # Note: Bucket versioning is not supported in minio-py 7.1.17
                # We'll handle versioning at the application level if needed
                if bucket_config["versioned"]:
                    logger.emit(
                        f"Bucket versioning configured for: {bucket_name}",
                        severity=Severity.INFO
                    )
            
        except Exception as e:
            logger.emit(
                "Failed to initialize buckets",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
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
            logger.emit(
                "File validation failed",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def _compress_data(self, data: bytes) -> bytes:
        """Compress data using gzip"""
        try:
            return gzip.compress(data)
        except Exception as e:
            logger.emit(
                "Data compression failed",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def _decompress_data(self, data: bytes) -> bytes:
        """Decompress gzipped data"""
        try:
            return gzip.decompress(data)
        except Exception as e:
            logger.emit(
                "Data decompression failed",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    @track_time(STORAGE_OPERATION_DURATION, {"operation_name": "store", "bucket": "unknown"})
    @track_errors(STORAGE_OPERATION_ERRORS, {"operation_name": "store", "bucket": "unknown", "error_type": "unknown"})
    async def store_file(
        self,
        user_id: str,
        data: BinaryIO,
        file_name: str,
        bucket_type: str,
        file_id: Optional[str] = None,
        compress: bool = True,
        chunk_size: int = 8 * 1024 * 1024,  # 8MB chunks
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        """Store file in bucket using streaming"""
        try:
            # Verify required services
            if not self.db or not self.key_mgmt or not self.encryption:
                raise ValueError("Required services not initialized")

            # Get bucket
            bucket = self.buckets[bucket_type]["name"]
            object_path = self._get_object_path(user_id, file_name)
            
            # Create temp file for processing
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp_path = temp.name
                
                # Get total size for progress tracking
                data.seek(0, 2)  # Seek to end
                total_size = data.tell()
                data.seek(0)  # Reset to start
                
                # Process file in chunks
                processed_size = 0
                chunks = []
                while True:
                    chunk = data.read(chunk_size)
                    if not chunk:
                        break
                    chunks.append(chunk)
                    processed_size += len(chunk)
                    
                    # Report progress
                    if progress_callback:
                        progress = (processed_size / total_size) * 100
                        await progress_callback(progress)
                
                # Validate file size
                if total_size > self.buckets[bucket_type]["max_size"]:
                    raise ValueError(
                        f"File too large for {bucket_type} bucket "
                        f"(max {self.buckets[bucket_type]['max_size']/1024/1024:.1f}MB)"
                    )
                
                # Combine chunks for processing
                file_data = b''.join(chunks)
                
                # Validate file type
                if self.buckets[bucket_type]["allowed_types"]:
                    mime = magic.Magic(mime=True)
                    detected_type = mime.from_buffer(file_data)
                    if detected_type not in self.buckets[bucket_type]["allowed_types"]:
                        raise ValueError(
                            f"Invalid file type for {bucket_type} bucket: {detected_type}"
                        )
                
                # Compress if requested (before encryption)
                processed_data = file_data
                if compress and bucket_type != "audio":  # Don't compress audio files
                    processed_data = self._compress_data(file_data)
                    file_name += ".gz"
                
                # Generate file key and encrypt data
                file_key = await self.key_mgmt.generate_key()
                encrypted_data = await self.encryption.encrypt(processed_data, file_key)
                
                # Derive user key and encrypt file key
                user_key = await self.key_mgmt.get_key(f"user_{user_id}")
                encrypted_key = await self.encryption.encrypt(file_key, user_key)
                
                # Store encrypted key
                file_key_create = FileKeyCreate(
                    file_id=file_id,
                    owner_id=user_id,
                    encrypted_key=encrypted_key
                )
                await self.db.create_file_key(file_key_create)
                
                # Write encrypted data to temp file
                with open(temp_path, 'wb') as f:
                    f.write(encrypted_data)
            
            try:
                # Upload file using multipart upload for large files
                if total_size > 64 * 1024 * 1024:  # Use multipart for files > 64MB
                    # Initialize multipart upload
                    upload_id = await asyncio.to_thread(
                        self.client.create_multipart_upload,
                        bucket,
                        object_path
                    )
                    
                    try:
                        # Upload parts
                        parts = []
                        with open(temp_path, 'rb') as f:
                            part_number = 1
                            while True:
                                part_data = f.read(chunk_size)
                                if not part_data:
                                    break
                                    
                                # Upload part
                                etag = await asyncio.to_thread(
                                    self.client.put_object,
                                    bucket,
                                    object_path,
                                    io.BytesIO(part_data),
                                    len(part_data),
                                    part_number=part_number,
                                    upload_id=upload_id
                                )
                                
                                parts.append({
                                    'PartNumber': part_number,
                                    'ETag': etag
                                })
                                part_number += 1
                        
                        # Complete multipart upload
                        await asyncio.to_thread(
                            self.client.complete_multipart_upload,
                            bucket,
                            object_path,
                            upload_id,
                            parts
                        )
                        
                    except Exception as e:
                        # Abort multipart upload on error
                        await asyncio.to_thread(
                            self.client.abort_multipart_upload,
                            bucket,
                            object_path,
                            upload_id
                        )
                        raise
                        
                else:
                    # Use single-part upload for smaller files
                    await asyncio.to_thread(
                        self.client.fput_object,
                        bucket,
                        object_path,
                        temp_path
                    )
                
                # Update storage metrics
                await self.update_bucket_size_metric(bucket_type)
                
                logger.emit(
                    "Stored encrypted file",
                    severity=Severity.INFO,
                    attributes={
                        "file_name": file_name,
                        "user_id": user_id,
                        "bucket": bucket_type
                    }
                )
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.emit(
                "Failed to store file",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_name": file_name,
                    "user_id": user_id,
                    "bucket": bucket_type
                }
            )
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
            # Verify required services
            if not self.db or not self.key_mgmt or not self.encryption:
                raise ValueError("Required services not initialized")

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
                
                # Get file key
                file_key_obj = await self.db.get_file_key(file_id)
                if not file_key_obj:
                    raise ValueError("File key not found")
                
                # Verify ownership/sharing
                if user_id != file_key_obj.owner_id:
                    share = await self.db.get_file_key_share(file_id, user_id)
                    if not share:
                        raise ValueError("Access denied")
                
                # Derive user key and decrypt file key
                user_key = await self.key_mgmt.get_key(f"user_{user_id}")
                file_key = await self.encryption.decrypt(file_key_obj.encrypted_key, user_key)
                
                # Decrypt data
                data = await self.encryption.decrypt(encrypted_data, file_key)
                
                # Decompress if needed
                if file_name.endswith(".gz"):
                    data = self._decompress_data(data)
                    
                return data
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.emit(
                "Failed to retrieve file",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_name": file_name,
                    "user_id": user_id,
                    "bucket": bucket_type,
                    "file_id": file_id
                }
            )
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
            
            logger.emit(
                "Deleted file",
                severity=Severity.INFO,
                attributes={
                    "file_name": file_name,
                    "user_id": user_id,
                    "bucket": bucket_type
                }
            )
            
        except Exception as e:
            logger.emit(
                "Failed to delete file",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "file_name": file_name,
                    "user_id": user_id,
                    "bucket": bucket_type
                }
            )
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
            logger.emit(
                "Failed to list files",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "user_id": user_id,
                    "bucket": bucket_type
                }
            )
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
            logger.emit(
                "Failed to get bucket size",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "bucket": bucket_type
                }
            )
            return 0

    async def update_bucket_size_metric(self, bucket_type: str):
        """Update storage metrics for bucket"""
        try:
            size = await self.get_bucket_size(bucket_type)
            update_gauge(STORAGE_BYTES, size, {"bucket": bucket_type})
        except Exception as e:
            logger.emit(
                "Failed to update storage metrics",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "bucket": bucket_type
                }
            )

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
            logger.emit(
                "Failed to cleanup temp files",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "max_age": max_age
                }
            )
            raise
