import os
from typing import Dict, Optional
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.fernet import Fernet
from ..services.encryption import EncryptionService

logger = logs.get_logger(__name__)

class KeyManagementService:
    def __init__(self):
        """Initialize key management service"""
        try:
            # Get master key (either from env or Azure Key Vault)
            self.encryption = EncryptionService()
            self.master_key = self.encryption.encryption_key.encode()
            
            # Initialize salt for key derivation
            self.salt = os.getenv("KEY_DERIVATION_SALT", "transcribo-key-salt").encode()
            
            logger.emit(
                "Key management service initialized",
                severity=Severity.INFO,
                attributes={"salt": self.salt.decode()}
            )
            
        except Exception as e:
            logger.emit(
                "Failed to initialize key management",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def derive_user_key(self, user_id: str) -> bytes:
        """Derive user-specific key from master key"""
        try:
            # Use HKDF to derive user key
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                info=f"user-{user_id}".encode()
            )
            
            return hkdf.derive(self.master_key)
            
        except Exception as e:
            logger.emit(
                "Failed to derive user key",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "user_id": user_id
                }
            )
            raise

    def generate_file_key(self) -> bytes:
        """Generate random key for file encryption"""
        try:
            return Fernet.generate_key()
        except Exception as e:
            logger.emit(
                "Failed to generate file key",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def encrypt_file_key(self, file_key: bytes, user_key: bytes) -> bytes:
        """Encrypt file key with user's key"""
        try:
            # Use user key to create Fernet instance
            f = Fernet(base64.urlsafe_b64encode(user_key))
            
            # Encrypt file key
            return f.encrypt(file_key)
            
        except Exception as e:
            logger.emit(
                "Failed to encrypt file key",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def decrypt_file_key(self, encrypted_key: bytes, user_key: bytes) -> bytes:
        """Decrypt file key with user's key"""
        try:
            # Use user key to create Fernet instance
            f = Fernet(base64.urlsafe_b64encode(user_key))
            
            # Decrypt file key
            return f.decrypt(encrypted_key)
            
        except Exception as e:
            logger.emit(
                "Failed to decrypt file key",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def encrypt_file(self, data: bytes, file_key: bytes) -> bytes:
        """Encrypt file data with file key"""
        try:
            # Use file key to create Fernet instance
            f = Fernet(file_key)
            
            # Encrypt data
            return f.encrypt(data)
            
        except Exception as e:
            logger.emit(
                "Failed to encrypt file",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def decrypt_file(self, encrypted_data: bytes, file_key: bytes) -> bytes:
        """Decrypt file data with file key"""
        try:
            # Use file key to create Fernet instance
            f = Fernet(file_key)
            
            # Decrypt data
            return f.decrypt(encrypted_data)
            
        except Exception as e:
            logger.emit(
                "Failed to decrypt file",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise

    def share_file_key(
        self,
        file_key: bytes,
        owner_key: bytes,
        recipient_key: bytes
    ) -> bytes:
        """Re-encrypt file key for sharing"""
        try:
            # First decrypt with owner's key
            decrypted_key = self.decrypt_file_key(file_key, owner_key)
            
            # Then encrypt with recipient's key
            return self.encrypt_file_key(decrypted_key, recipient_key)
            
        except Exception as e:
            logger.emit(
                "Failed to share file key",
                severity=Severity.ERROR,
                attributes={"error": str(e)}
            )
            raise
