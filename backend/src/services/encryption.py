"""Encryption service."""

import logging
import os
import secrets
from typing import Dict, Optional, Any, TypedDict, cast
from datetime import datetime
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidKey
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import EncryptionError, TranscriboError
from ..types import ServiceConfig, ErrorContext, JSONValue
from .base import BaseService
from ..utils.metrics import (
    ENCRYPTION_OPERATIONS,
    ENCRYPTION_ERRORS,
    ENCRYPTION_LATENCY,
    track_encryption_operation,
    track_encryption_error,
    track_encryption_latency
)

class EncryptionMetadata(TypedDict):
    """Type definition for encryption metadata."""
    algorithm: str
    nonce: bytes
    version: str

class EncryptionResult(TypedDict):
    """Type definition for encryption result."""
    encrypted_data: bytes
    metadata: EncryptionMetadata

class EncryptionService(BaseService):
    """Service for handling file encryption and decryption."""

    def __init__(self, settings: ServiceConfig) -> None:
        """Initialize encryption service.
        
        Args:
            settings: Service configuration
        """
        super().__init__(settings)
        self.algorithm: str = 'AES-256-GCM'
        self.key_size: int = 256
        self.chunk_size: int = 8192

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize encryption settings
            self.algorithm = self.settings.get('encryption_algorithm', 'AES-256-GCM')
            self.key_size = int(self.settings.get('encryption_key_size', 256))
            self.chunk_size = int(self.settings.get('encryption_chunk_size', 8192))

            log_info("Encryption service initialized")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_encryption",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize encryption service: {str(e)}")
            raise TranscriboError(
                "Failed to initialize encryption service",
                details=error_context
            )

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
        try:
            log_info("Encryption service cleaned up")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_encryption",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during encryption service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up encryption service",
                details=error_context
            )

    async def encrypt_file(self, file_data: bytes, key: bytes) -> EncryptionResult:
        """Encrypt file data.
        
        Args:
            file_data: Raw file data to encrypt
            key: Encryption key
            
        Returns:
            Dictionary containing encrypted data and metadata
            
        Raises:
            EncryptionError: If encryption fails
        """
        start_time = logging.time()
        try:
            self._check_initialized()

            # Track operation
            ENCRYPTION_OPERATIONS.labels(operation='encrypt').inc()
            track_encryption_operation('encrypt')

            # Encrypt data
            result = await self._encrypt_data(file_data, key)
            
            # Track latency
            duration = logging.time() - start_time
            ENCRYPTION_LATENCY.observe(duration)
            track_encryption_latency(duration)
            
            log_info(f"Encrypted {len(file_data)} bytes")
            return result

        except Exception as e:
            ENCRYPTION_ERRORS.inc()
            track_encryption_error()
            error_context: ErrorContext = {
                "operation": "encrypt_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "data_size": len(file_data)
                }
            }
            log_error(f"Error encrypting file: {str(e)}")
            raise EncryptionError("Failed to encrypt file", details=error_context)

    async def decrypt_file(
        self,
        encrypted_data: bytes,
        key: bytes,
        metadata: EncryptionMetadata
    ) -> bytes:
        """Decrypt file data.
        
        Args:
            encrypted_data: Encrypted file data
            key: Decryption key
            metadata: Encryption metadata
            
        Returns:
            Decrypted file data
            
        Raises:
            EncryptionError: If decryption fails
        """
        start_time = logging.time()
        try:
            self._check_initialized()

            # Track operation
            ENCRYPTION_OPERATIONS.labels(operation='decrypt').inc()
            track_encryption_operation('decrypt')

            # Decrypt data
            decrypted_data = await self._decrypt_data(encrypted_data, key, metadata)
            
            # Track latency
            duration = logging.time() - start_time
            ENCRYPTION_LATENCY.observe(duration)
            track_encryption_latency(duration)
            
            log_info(f"Decrypted {len(encrypted_data)} bytes")
            return decrypted_data

        except Exception as e:
            ENCRYPTION_ERRORS.inc()
            track_encryption_error()
            error_context: ErrorContext = {
                "operation": "decrypt_file",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "data_size": len(encrypted_data)
                }
            }
            log_error(f"Error decrypting file: {str(e)}")
            raise EncryptionError("Failed to decrypt file", details=error_context)

    async def generate_key(self) -> bytes:
        """Generate a new encryption key.
        
        Returns:
            Generated encryption key
            
        Raises:
            EncryptionError: If key generation fails
        """
        try:
            self._check_initialized()

            # Track operation
            ENCRYPTION_OPERATIONS.labels(operation='generate_key').inc()
            track_encryption_operation('generate_key')

            # Generate key
            key = await self._generate_key()
            log_info("Generated new encryption key")
            return key

        except Exception as e:
            ENCRYPTION_ERRORS.inc()
            track_encryption_error()
            error_context: ErrorContext = {
                "operation": "generate_key",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error generating encryption key: {str(e)}")
            raise EncryptionError("Failed to generate key", details=error_context)

    async def validate_key(self, key: bytes) -> bool:
        """Validate an encryption key.
        
        Args:
            key: Encryption key to validate
            
        Returns:
            True if key is valid, False otherwise
            
        Raises:
            EncryptionError: If validation fails
        """
        try:
            self._check_initialized()

            # Track operation
            ENCRYPTION_OPERATIONS.labels(operation='validate_key').inc()
            track_encryption_operation('validate_key')

            # Validate key
            is_valid = await self._validate_key(key)
            
            if is_valid:
                log_info("Validated encryption key")
            else:
                log_warning("Invalid encryption key")
            
            return is_valid

        except Exception as e:
            ENCRYPTION_ERRORS.inc()
            track_encryption_error()
            error_context: ErrorContext = {
                "operation": "validate_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "key_length": len(key)
                }
            }
            log_error(f"Error validating encryption key: {str(e)}")
            raise EncryptionError("Failed to validate key", details=error_context)

    async def _encrypt_data(self, data: bytes, key: bytes) -> EncryptionResult:
        """Encrypt data with key using AES-GCM.
        
        Args:
            data: Data to encrypt
            key: Encryption key
            
        Returns:
            Dictionary containing encrypted data and metadata
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Generate a random 96-bit nonce
            nonce = os.urandom(12)
            
            # Create AESGCM cipher
            cipher = AESGCM(key)
            
            # Encrypt data with authenticated encryption
            encrypted_data = cipher.encrypt(nonce, data, None)
            
            return {
                'encrypted_data': encrypted_data,
                'metadata': {
                    'algorithm': 'AES-GCM',
                    'nonce': nonce,
                    'version': '1.0'
                }
            }
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "encrypt_data",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
            log_error(f"Encryption error: {type(e).__name__}")
            raise EncryptionError("Failed to encrypt data", details=error_context)

    async def _decrypt_data(
        self,
        encrypted_data: bytes,
        key: bytes,
        metadata: EncryptionMetadata
    ) -> bytes:
        """Decrypt data with key using AES-GCM.
        
        Args:
            encrypted_data: Data to decrypt
            key: Decryption key
            metadata: Encryption metadata
            
        Returns:
            Decrypted data
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            # Validate metadata
            if not metadata or 'nonce' not in metadata:
                raise ValueError("Invalid metadata: missing nonce")
            
            # Create AESGCM cipher
            cipher = AESGCM(key)
            
            # Decrypt data with authenticated decryption
            decrypted_data = cipher.decrypt(metadata['nonce'], encrypted_data, None)
            
            return decrypted_data
        except InvalidKey:
            error_context: ErrorContext = {
                "operation": "decrypt_data",
                "timestamp": datetime.utcnow(),
                "details": {"error": "Invalid encryption key"}
            }
            log_error("Invalid encryption key")
            raise EncryptionError("Invalid encryption key", details=error_context)
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "decrypt_data",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
            log_error(f"Decryption error: {type(e).__name__}")
            raise EncryptionError("Failed to decrypt data", details=error_context)

    async def _generate_key(self) -> bytes:
        """Generate a secure encryption key using PBKDF2.
        
        Returns:
            Generated encryption key
            
        Raises:
            EncryptionError: If key generation fails
        """
        try:
            # Generate a random salt
            salt = os.urandom(16)
            
            # Generate a random password
            password = secrets.token_bytes(32)
            
            # Use PBKDF2 to derive a key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,  # 256-bit key
                salt=salt,
                iterations=100000,
            )
            
            # Derive the key
            key = kdf.derive(password)
            
            return key
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "generate_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            }
            log_error(f"Key generation error: {type(e).__name__}")
            raise EncryptionError("Failed to generate encryption key", details=error_context)

    async def _validate_key(self, key: bytes) -> bool:
        """Validate encryption key.
        
        Args:
            key: Key to validate
            
        Returns:
            True if key is valid, False otherwise
        """
        try:
            # Check key length
            if len(key) != 32:  # 256 bits
                log_warning(f"Invalid key length: {len(key)} bytes")
                return False
            
            # Test key with a sample encryption
            test_data = b"test"
            nonce = os.urandom(12)
            cipher = AESGCM(key)
            
            try:
                # Try to encrypt and decrypt test data
                encrypted = cipher.encrypt(nonce, test_data, None)
                decrypted = cipher.decrypt(nonce, encrypted, None)
                
                # Verify decryption was successful
                return decrypted == test_data
            except Exception:
                return False
                
        except Exception as e:
            log_error(f"Key validation error: {type(e).__name__}")
            return False
