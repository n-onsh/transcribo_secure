import os
import logging
from typing import Optional, Dict, List, BinaryIO
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json

logger = logging.getLogger(__name__)

class EncryptionService:
    def __init__(self):
        """Initialize encryption service"""
        try:
            print("DEBUG: Starting encryption service initialization...")
            
            # Initialize variables
            self.encryption_key = os.getenv("ENCRYPTION_KEY")
            self.salt = os.getenv("ENCRYPTION_SALT", "transcribo-salt").encode()
            self.fernet = None
            
            # If local encryption key is provided, use it and skip Azure Key Vault
            if self.encryption_key:
                print("DEBUG: Using local encryption key")
                try:
                    self.fernet = Fernet(self.encryption_key.encode())
                    logger.info("Encryption service initialized with local key")
                    return
                except Exception as e:
                    logger.error(f"Failed to initialize with local key: {str(e)}")
                    raise ValueError("Invalid ENCRYPTION_KEY format. Must be base64-encoded 32 byte key.")

            # Only proceed with Azure Key Vault setup if no local key
            print("DEBUG: No local key found, proceeding with Azure Key Vault")
            self.key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
            self.key_name = os.getenv("ENCRYPTION_KEY_NAME", "data-encryption-key")
            
            print(f"DEBUG: Key vault URL: {self.key_vault_url}")
            print(f"DEBUG: Key name: {self.key_name}")
            print(f"DEBUG: Azure Tenant ID: {os.getenv('AZURE_TENANT_ID')}")
            print(f"DEBUG: Azure Client ID: {os.getenv('AZURE_CLIENT_ID')}")
            print(f"DEBUG: Azure Client Secret: {os.getenv('AZURE_CLIENT_SECRET')}")
            
            # Validate all required environment variables upfront
            required_vars = {
                'AZURE_KEYVAULT_URL': self.key_vault_url,
                'AZURE_TENANT_ID': os.getenv('AZURE_TENANT_ID'),
                'AZURE_CLIENT_ID': os.getenv('AZURE_CLIENT_ID'),
                'AZURE_CLIENT_SECRET': os.getenv('AZURE_CLIENT_SECRET')
            }
            
            missing_vars = [k for k, v in required_vars.items() if not v]
            if missing_vars:
                raise ValueError(
                    f"Missing required environment variables: {', '.join(missing_vars)}\n"
                    "These variables are needed for Azure Key Vault access. "
                    "Please check techContext.md for configuration details."
                )
            
            # Initialize Azure credentials
            print("DEBUG: Initializing Azure credentials...")
            try:
                from azure.identity._credentials.environment import EnvironmentCredential
                try:
                    credential = EnvironmentCredential()
                    print("DEBUG: EnvironmentCredential initialized successfully")
                except Exception as e:
                    print(f"DEBUG: EnvironmentCredential failed: {str(e)}")
                    print("DEBUG: Falling back to DefaultAzureCredential...")
                    credential = DefaultAzureCredential()
                    print("DEBUG: DefaultAzureCredential initialized successfully")
            except Exception as e:
                raise ValueError(
                    "Failed to initialize Azure credentials. This could be due to:\n"
                    "1. Invalid credentials in environment variables\n"
                    "2. Network connectivity issues\n"
                    "3. Azure AD authentication problems\n"
                    f"Original error: {str(e)}"
                )
            
            # Initialize Key Vault client
            print("DEBUG: Creating SecretClient...")
            try:
                self.key_vault = SecretClient(
                    vault_url=self.key_vault_url,
                    credential=credential
                )
                print("DEBUG: SecretClient created successfully")
            except Exception as e:
                raise ValueError(
                    "Failed to create Key Vault client. This could be due to:\n"
                    "1. Invalid Key Vault URL\n"
                    "2. Network connectivity issues\n"
                    "3. Missing RBAC permissions - ensure the application has:\n"
                    "   - Key Vault Secrets User role for reading secrets\n"
                    "   - Key Vault Secrets Officer role for setting secrets\n"
                    f"Original error: {str(e)}"
                )
            
            # Initialize encryption key
            self.fernet = None
            self._init_encryption()
            
            logger.info("Encryption service initialized")
            
        except Exception as e:
            print(f"DEBUG: Error initializing encryption service: {str(e)}")
            logger.error(f"Failed to initialize encryption service: {str(e)}")
            raise

    def _init_encryption(self):
        """Initialize encryption key from Azure Key Vault"""
        try:
            # Get key from Key Vault
            try:
                secret = self.key_vault.get_secret(self.key_name)
                key = secret.value
            except Exception:
                # Generate new key if not exists
                key = self._generate_key()
                self.key_vault.set_secret(self.key_name, key)
            
            # Initialize Fernet
            self.fernet = Fernet(key.encode())
            
        except Exception as e:
            logger.error(f"Failed to initialize encryption: {str(e)}")
            raise

    def _generate_key(self) -> str:
        """Generate new encryption key"""
        try:
            # Generate key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self.salt,
                iterations=100000
            )
            key = base64.urlsafe_b64encode(kdf.derive(os.urandom(32)))
            return key.decode()
            
        except Exception as e:
            logger.error(f"Failed to generate key: {str(e)}")
            raise

    def rotate_key(self):
        """Rotate encryption key"""
        try:
            # Generate new key
            new_key = self._generate_key()
            
            # Store in Key Vault
            self.key_vault.set_secret(self.key_name, new_key)
            
            # Update Fernet
            self.fernet = Fernet(new_key.encode())
            
            logger.info("Encryption key rotated")
            
        except Exception as e:
            logger.error(f"Failed to rotate key: {str(e)}")
            raise

    def encrypt_string(self, data: str) -> str:
        """Encrypt string data"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt string: {str(e)}")
            raise

    def decrypt_string(self, data: str) -> str:
        """Decrypt string data"""
        try:
            return self.fernet.decrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt string: {str(e)}")
            raise

    def encrypt_dict(self, data: Dict) -> str:
        """Encrypt dictionary data"""
        try:
            json_str = json.dumps(data)
            return self.encrypt_string(json_str)
        except Exception as e:
            logger.error(f"Failed to encrypt dict: {str(e)}")
            raise

    def decrypt_dict(self, data: str) -> Dict:
        """Decrypt dictionary data"""
        try:
            json_str = self.decrypt_string(data)
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to decrypt dict: {str(e)}")
            raise

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt binary data"""
        try:
            return self.fernet.encrypt(data)
        except Exception as e:
            logger.error(f"Failed to encrypt bytes: {str(e)}")
            raise

    def decrypt_bytes(self, data: bytes) -> bytes:
        """Decrypt binary data"""
        try:
            return self.fernet.decrypt(data)
        except Exception as e:
            logger.error(f"Failed to decrypt bytes: {str(e)}")
            raise

    def encrypt_file(self, input_path: str, output_path: str):
        """Encrypt file"""
        try:
            # Read input file
            with open(input_path, "rb") as f:
                data = f.read()
            
            # Encrypt data
            encrypted = self.encrypt_bytes(data)
            
            # Write output file
            with open(output_path, "wb") as f:
                f.write(encrypted)
                
        except Exception as e:
            logger.error(f"Failed to encrypt file: {str(e)}")
            raise

    def decrypt_file(self, input_path: str, output_path: str):
        """Decrypt file"""
        try:
            # Read input file
            with open(input_path, "rb") as f:
                data = f.read()
            
            # Decrypt data
            decrypted = self.decrypt_bytes(data)
            
            # Write output file
            with open(output_path, "wb") as f:
                f.write(decrypted)
                
        except Exception as e:
            logger.error(f"Failed to decrypt file: {str(e)}")
            raise

    def encrypt_stream(self, stream: BinaryIO) -> bytes:
        """Encrypt stream data"""
        try:
            return self.encrypt_bytes(stream.read())
        except Exception as e:
            logger.error(f"Failed to encrypt stream: {str(e)}")
            raise

    def decrypt_stream(self, stream: BinaryIO) -> bytes:
        """Decrypt stream data"""
        try:
            return self.decrypt_bytes(stream.read())
        except Exception as e:
            logger.error(f"Failed to decrypt stream: {str(e)}")
            raise

    def encrypt_metadata(self, metadata: Dict) -> Dict:
        """Encrypt sensitive metadata fields"""
        try:
            # Define sensitive fields
            sensitive_fields = {
                "email",
                "phone",
                "address",
                "notes",
                "comments"
            }
            
            # Encrypt sensitive fields
            encrypted = {}
            for key, value in metadata.items():
                if key in sensitive_fields and value:
                    encrypted[key] = self.encrypt_string(str(value))
                else:
                    encrypted[key] = value
            
            return encrypted
            
        except Exception as e:
            logger.error(f"Failed to encrypt metadata: {str(e)}")
            raise

    def decrypt_metadata(self, metadata: Dict) -> Dict:
        """Decrypt sensitive metadata fields"""
        try:
            # Define sensitive fields
            sensitive_fields = {
                "email",
                "phone",
                "address",
                "notes",
                "comments"
            }
            
            # Decrypt sensitive fields
            decrypted = {}
            for key, value in metadata.items():
                if key in sensitive_fields and value:
                    decrypted[key] = self.decrypt_string(value)
                else:
                    decrypted[key] = value
            
            return decrypted
            
        except Exception as e:
            logger.error(f"Failed to decrypt metadata: {str(e)}")
            raise
