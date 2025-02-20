import os
import logging
from typing import Optional, Dict, List, BinaryIO
from minio import Minio
from minio.error import S3Error
from datetime import datetime, timedelta
import tempfile
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        """Initialize storage service"""
        # Get configuration
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        self.region = os.getenv("MINIO_REGION", "us-east-1")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        if not self.access_key or not self.secret_key:
            raise ValueError("MinIO credentials not set")
        
        # Initialize client
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            region=self.region,
            secure=self.secure
        )
        
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
        
        # Initialize buckets
        self._init_buckets()
        
        logger.info("Storage service initialized")

    def _init_buckets(self):
        """Initialize storage buckets"""
        try:
            for bucket_config in self.buckets.values():
                bucket_name = bucket_config["name"]
                if not self.client.bucket_exists(bucket_name):
                    self.client.make_bucket(bucket_name)
                    logger.info(f"Created bucket: {bucket_name}")
                
                # Enable versioning for critical buckets
                if bucket_config["versioned"]:
                    self.client.set_bucket_versioning(bucket_name, enabled=True)
                    logger.info(f"Enabled versioning for bucket: {bucket_name}")
            
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

    async def store_file(
        self,
        user_id: str,
        data: bytes,
        file_name: str,
        bucket_type: str,
        compress: bool = True
    ):
        """Store file in bucket"""
        try:
            # Validate file
            self._validate_file(data, file_name, bucket_type)
            
            # Get bucket
            bucket = self.buckets[bucket_type]["name"]
            
            # Compress data if requested
            if compress and bucket_type != "audio":  # Don't compress audio files
                data = self._compress_data(data)
                file_name += ".gz"
            
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False) as temp:
                temp.write(data)
                temp_path = temp.name
            
            try:
                # Upload file
                object_path = self._get_object_path(user_id, file_name)
                self.client.fput_object(
                    bucket,
                    object_path,
                    temp_path
                )
                
                logger.info(f"Stored file {file_name} for user {user_id}")
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Failed to store file: {str(e)}")
            raise

    async def retrieve_file(
        self,
        user_id: str,
        file_name: str,
        bucket_type: str,
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
                self.client.fget_object(
                    bucket,
                    object_path,
                    temp_path,
                    version_id=version_id
                )
                
                # Read file
                with open(temp_path, "rb") as f:
                    data = f.read()
                
                # Decompress if needed
                if file_name.endswith(".gz"):
                    data = self._decompress_data(data)
                    
                return data
                
            finally:
                # Clean up temp file
                os.unlink(temp_path)
            
        except Exception as e:
            logger.error(f"Failed to retrieve file: {str(e)}")
            raise

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
            self.client.remove_object(bucket, object_path)
            
            logger.info(f"Deleted file {file_name} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to delete file: {str(e)}")
            raise

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
                objects = self.client.list_objects_versions(bucket, prefix=prefix)
            else:
                objects = self.client.list_objects(bucket, prefix=prefix)
            
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

    async def get_presigned_url(
        self,
        user_id: str,
        file_name: str,
        bucket_type: str,
        expires_in: int = 3600
    ) -> str:
        """Get presigned URL for file"""
        try:
            # Get bucket
            bucket = self.buckets.get(bucket_type)
            if not bucket:
                raise ValueError(f"Invalid bucket type: {bucket_type}")
            
            # Get URL
            object_path = self._get_object_path(user_id, file_name)
            url = self.client.presigned_get_object(
                bucket,
                object_path,
                expires=timedelta(seconds=expires_in)
            )
            
            return url
            
        except Exception as e:
            logger.error(f"Failed to get presigned URL: {str(e)}")
            raise

    async def copy_file(
        self,
        user_id: str,
        file_name: str,
        source_bucket: str,
        dest_bucket: str
    ):
        """Copy file between buckets"""
        try:
            # Get buckets
            source = self.buckets.get(source_bucket)
            dest = self.buckets.get(dest_bucket)
            if not source or not dest:
                raise ValueError("Invalid bucket type")
            
            # Copy file
            object_path = self._get_object_path(user_id, file_name)
            self.client.copy_object(
                dest,
                object_path,
                f"{source}/{object_path}"
            )
            
            logger.info(f"Copied file {file_name} for user {user_id}")
            
        except Exception as e:
            logger.error(f"Failed to copy file: {str(e)}")
            raise

    async def move_file(
        self,
        user_id: str,
        file_name: str,
        source_bucket: str,
        dest_bucket: str
    ):
        """Move file between buckets"""
        try:
            # Copy file
            await self.copy_file(user_id, file_name, source_bucket, dest_bucket)
            
            # Delete original
            await self.delete_file(user_id, file_name, source_bucket)
            
        except Exception as e:
            logger.error(f"Failed to move file: {str(e)}")
            raise

    async def cleanup_temp_files(self, max_age: int = 24):
        """Clean up old temp files"""
        try:
            # Get temp bucket
            bucket = self.buckets["temp"]
            
            # List objects
            objects = self.client.list_objects(bucket)
            
            # Delete old files
            cutoff = datetime.utcnow() - timedelta(hours=max_age)
            for obj in objects:
                if obj.last_modified < cutoff:
                    self.client.remove_object(bucket, obj.object_name)
            
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {str(e)}")
            raise
