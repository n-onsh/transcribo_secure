"""File encryption service."""

import os
import io
from uuid import UUID
from datetime import datetime
from typing import Dict, Optional, Any, BinaryIO, Tuple
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    track_encryption_operation,
    track_encryption_error,
    track_encryption_latency,
    track_encryption_file_size
)
from ..types import ErrorContext
from ..utils.exceptions import EncryptionError
from .base import BaseService
from .file_key_service import FileKeyService
from ..config import config

class EncryptionService(BaseService):
    """Service for file encryption operations."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize service.
        
        Args:
            settings: Service settings
        """
        super().__init__(settings)
        self.config = config.storage.encryption
        self.key_service: Optional[FileKeyService] = None
        self.chunk_size = self.config.chunk_size_mb * 1024 * 1024  # Convert MB to bytes

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            if not self.config.enabled:
                log_info("Encryption disabled")
                return

            # Get key service
            from .provider import service_provider
            self.key_service = service_provider.get(FileKeyService)
            if not self.key_service:
                raise EncryptionError("File key service not available")

            # Initialize key service if needed
            if not self.key_service.initialized:
                await self.key_service.initialize()

            log_info("Encryption service initialized", {
                "chunk_size": f"{self.config.chunk_size_mb}MB",
                "algorithm": self.config.algorithm
            })

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_encryption",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize encryption service: {str(e)}")
            raise EncryptionError(
                "Failed to initialize encryption service",
                details=error_context
            )

    async def encrypt_file(
        self,
        file_id: UUID,
        input_file: BinaryIO,
        output_file: BinaryIO
    ) -> None:
        """Encrypt a file using authenticated encryption.
        
        Args:
            file_id: File ID for key lookup
            input_file: Input file object
            output_file: Output file object
            
        Raises:
            EncryptionError: If encryption fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('encrypt_file')

            # Generate IV
            iv = os.urandom(12)  # 96 bits for GCM

            # Get encryption key
            key = await self.key_service.get_key(file_id)
            if not key:
                key = await self.key_service.generate_key(file_id)

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),  # Use GCM for authenticated encryption
                backend=default_backend()
            )
            encryptor = cipher.encryptor()

            # Write IV
            output_file.write(iv)

            # Encrypt in chunks
            file_size = 0
            while True:
                chunk = input_file.read(self.chunk_size)
                if not chunk:
                    break

                file_size += len(chunk)

                # Encrypt chunk
                encrypted_chunk = encryptor.update(chunk)
                output_file.write(encrypted_chunk)

            # Write final block and authentication tag
            final_chunk = encryptor.finalize()
            if final_chunk:
                output_file.write(final_chunk)
            
            # Write authentication tag
            output_file.write(encryptor.tag)

            # Track file size
            track_encryption_file_size(file_size)

            log_info(f"Encrypted file {file_id}", {
                "size": file_size,
                "chunks": (file_size + self.chunk_size - 1) // self.chunk_size
            })

        except Exception as e:
            # Track error
            track_encryption_error('encrypt_file')

            error_context: ErrorContext = {
                "operation": "encrypt_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to encrypt file {file_id}: {str(e)}")
            raise EncryptionError(
                f"Failed to encrypt file: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'encrypt_file')

    async def decrypt_file(
        self,
        file_id: UUID,
        input_file: BinaryIO,
        output_file: BinaryIO
    ) -> None:
        """Decrypt a file using authenticated encryption.
        
        Args:
            file_id: File ID for key lookup
            input_file: Input file object
            output_file: Output file object
            
        Raises:
            EncryptionError: If decryption fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('decrypt_file')

            # Read IV
            iv = input_file.read(12)  # 96 bits for GCM
            if len(iv) != 12:
                raise EncryptionError("Invalid encrypted file format")

            # Get decryption key
            key = await self.key_service.get_key(file_id)
            if not key:
                raise EncryptionError(f"No key found for file {file_id}")

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()

            # Read file into memory to get tag
            data = input_file.read()
            if len(data) < 16:  # At least 16 bytes for tag
                raise EncryptionError("Invalid encrypted file format")

            # Split data and tag
            ciphertext = data[:-16]
            tag = data[-16:]

            # Set tag
            decryptor.authenticate_additional_data(b"")

            # Decrypt in chunks
            file_size = len(ciphertext)
            pos = 0
            while pos < file_size:
                chunk = ciphertext[pos:pos + self.chunk_size]
                decrypted_chunk = decryptor.update(chunk)
                output_file.write(decrypted_chunk)
                pos += len(chunk)

            # Verify tag and finalize
            decryptor.authenticate_additional_data(b"")
            decryptor.tag = tag
            final_chunk = decryptor.finalize()
            if final_chunk:
                output_file.write(final_chunk)

            # Track file size
            track_encryption_file_size(file_size)

            log_info(f"Decrypted file {file_id}", {
                "size": file_size,
                "chunks": (file_size + self.chunk_size - 1) // self.chunk_size
            })

        except Exception as e:
            # Track error
            track_encryption_error('decrypt_file')

            error_context: ErrorContext = {
                "operation": "decrypt_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "file_id": str(file_id)
                }
            }
            log_error(f"Failed to decrypt file {file_id}: {str(e)}")
            raise EncryptionError(
                f"Failed to decrypt file: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'decrypt_file')

    async def rotate_file_key(
        self,
        file_id: UUID,
        input_file: BinaryIO,
        output_file: BinaryIO
    ) -> None:
        """Rotate encryption key for a file.
        
        This re-encrypts the file with a new key.
        
        Args:
            file_id: File ID to rotate key for
            input_file: Input file object
            output_file: Output file object
            
        Raises:
            EncryptionError: If key rotation fails
        """
        self._check_initialized()
        start_time = datetime.utcnow()

        try:
            # Track operation
            track_encryption_operation('rotate_key')

            # Create temporary buffer
            temp_buffer = io.BytesIO()

            # Decrypt with old key
            await self.decrypt_file(file_id, input_file, temp_buffer)

            # Rotate key
            await self.key_service.rotate_key(file_id)

            # Reset buffer for reading
            temp_buffer.seek(0)

            # Encrypt with new key
            await self.encrypt_file(file_id, temp_buffer, output_file)

            log_info(f"Rotated key for file {file_id}")

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
            raise EncryptionError(
                f"Failed to rotate key: {str(e)}",
                details=error_context
            )

        finally:
            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            track_encryption_latency(duration, 'rotate_key')
