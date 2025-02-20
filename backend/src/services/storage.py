from minio import Minio
from minio.error import S3Error
import os
from uuid import UUID
from typing import BinaryIO, Optional, Dict
from .encryption import EncryptionService
import io
import hashlib
from ..config import get_settings
import asyncio
from fastapi import HTTPException

class StorageService:
    def __init__(self):
        self.settings = get_settings()
        self.client = Minio(
            f"{self.settings.MINIO_HOST}:{self.settings.MINIO_PORT}",
            access_key=self.settings.MINIO_ACCESS_KEY,
            secret_key=self.settings.MINIO_SECRET_KEY,
            secure=self.settings.MINIO_SECURE
        )
        self.encryption = EncryptionService()
        self.buckets = {
            'input': 'input-files',
            'output': 'output-files',
            'error': 'error-files'
        }

    async def init_buckets(self):
        """Ensure all required buckets exist."""
        for bucket in self.buckets.values():
            try:
                if not self.client.bucket_exists(bucket):
                    self.client.make_bucket(bucket)
                    # Enable versioning for additional safety
                    self.client.set_bucket_versioning(bucket, True)
            except S3Error as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to initialize bucket {bucket}: {str(e)}"
                )

    async def store_file(
        self,
        file_id: UUID,
        file_data: BinaryIO,
        file_name: str,
        file_type: str,
        metadata: Optional[Dict] = None
    ) -> int:
        """Store an encrypted file in MinIO with proper chunking for large files."""
        bucket_name = self.buckets[file_type]
        object_name = f"{file_id}/{file_name}"
        
        # Calculate file hash for integrity checking
        file_hash = hashlib.sha256()
        
        # Read file in chunks
        chunks = []
        total_size = 0
        chunk_size = self.settings.CHUNK_SIZE
        
        while True:
            chunk = file_data.read(chunk_size)
            if not chunk:
                break
            file_hash.update(chunk)
            chunks.append(chunk)
            total_size += len(chunk)

        if total_size > self.settings.MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File too large"
            )

        # Combine chunks and encrypt
        combined_data = b''.join(chunks)
        encrypted_data = await self.encryption.encrypt_data(combined_data)
        
        # Store file metadata including hash
        file_metadata = metadata or {}
        file_metadata.update({
            'sha256': file_hash.hexdigest(),
            'original_size': total_size,
            'encrypted_size': len(encrypted_data)
        })

        # Create BytesIO object with encrypted data
        encrypted_io = io.BytesIO(encrypted_data)
        
        try:
            # Store encrypted file with metadata
            self.client.put_object(
                bucket_name,
                object_name,
                encrypted_io,
                len(encrypted_data),
                metadata=file_metadata,
                content_type=file_type
            )
            return total_size
        except S3Error as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store file: {str(e)}"
            )

    async def retrieve_file(
        self,
        file_id: UUID,
        file_name: str,
        file_type: str
    ) -> Optional[BinaryIO]:
        """Retrieve and decrypt a file from MinIO."""
        try:
            bucket_name = self.buckets[file_type]
            object_name = f"{file_id}/{file_name}"
            
            # Get file and metadata
            obj = self.client.get_object(bucket_name, object_name)
            encrypted_data = obj.read()
            
            # Verify metadata
            stored_metadata = obj.metadata()
            if 'sha256' in stored_metadata:
                original_hash = stored_metadata['sha256']
                
                # Decrypt data
                decrypted_data = await self.encryption.decrypt_data(encrypted_data)
                
                # Verify hash
                current_hash = hashlib.sha256(decrypted_data).hexdigest()
                if current_hash != original_hash:
                    raise HTTPException(
                        status_code=500,
                        detail="File integrity check failed"
                    )
                
                return io.BytesIO(decrypted_data)
            
            # If no hash in metadata (legacy files), just decrypt
            decrypted_data = await self.encryption.decrypt_data(encrypted_data)
            return io.BytesIO(decrypted_data)
            
        except S3Error as e:
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving file: {str(e)}"
            )

    async def delete_file(
        self,
        file_id: UUID,
        file_name: str,
        file_type: str
    ) -> bool:
        """Delete a file from storage."""
        try:
            bucket_name = self.buckets[file_type]
            object_name = f"{file_id}/{file_name}"
            self.client.remove_object(bucket_name, object_name)
            return True
        except S3Error as e:
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {str(e)}"
            )