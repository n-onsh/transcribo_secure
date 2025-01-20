from minio import Minio
import os
from uuid import UUID
from typing import BinaryIO, Optional
from .encryption import EncryptionService
import io

class StorageService:
    def __init__(self):
        self.client = Minio(
            f"{os.getenv('MINIO_HOST')}:{os.getenv('MINIO_PORT')}",
            access_key=os.getenv('MINIO_ACCESS_KEY'),
            secret_key=os.getenv('MINIO_SECRET_KEY'),
            secure=False  # Set to True in production with proper certificates
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
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)

    async def store_file(self, file_id: UUID, file_data: BinaryIO, file_name: str, file_type: str) -> int:
        """Store an encrypted file in MinIO and return its size."""
        bucket_name = self.buckets[file_type]
        
        # Read and encrypt file data
        raw_data = file_data.read()
        encrypted_data = await self.encryption.encrypt_data(raw_data)
        
        # Create a new BytesIO object with encrypted data
        encrypted_io = io.BytesIO(encrypted_data)
        size = len(encrypted_data)
        
        # Store encrypted file
        self.client.put_object(
            bucket_name,
            f"{file_id}/{file_name}",
            encrypted_io,
            size
        )
        return size

    async def retrieve_file(self, file_id: UUID, file_name: str, file_type: str) -> Optional[BinaryIO]:
        """Retrieve and decrypt a file from MinIO."""
        try:
            bucket_name = self.buckets[file_type]
            encrypted_data = self.client.get_object(bucket_name, f"{file_id}/{file_name}").read()
            
            # Decrypt data
            decrypted_data = await self.encryption.decrypt_data(encrypted_data)
            
            # Return as BytesIO object
            return io.BytesIO(decrypted_data)
        except Exception as e:
            print(f"Error retrieving file: {e}")
            return None