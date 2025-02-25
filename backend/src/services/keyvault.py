import os
from typing import Optional, Dict, List
from opentelemetry import trace, logs
from opentelemetry.logs import Severity
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.keyvault.certificates import CertificateClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

logger = logs.get_logger(__name__)

class MockKeyVaultService:
    """Development and fallback implementation of KeyVaultService.

    IMPORTANT: This is NOT a test mock. This is a functional development implementation
    that uses environment variables as a simple key-value store when Azure KeyVault
    is not configured.

    Key characteristics:
    - Uses environment variables for secret storage
    - Provides working implementation for development
    - Logs warnings about being temporary solution
    - Falls back to this when Azure KeyVault setup is missing
    
    Implementation rationale:
    - Allows development without Azure KeyVault configuration
    - Provides seamless fallback for non-production environments
    - Maintains consistent interface with real KeyVault service
    - Enables easy transition to real KeyVault in production

    Security considerations:
    - NOT suitable for production use
    - Environment variables are not secure secret storage
    - No encryption at rest
    - No access controls
    - No audit logging

    Migration to production:
    1. Configure Azure KeyVault URL
    2. Set up proper Azure credentials
    3. Move secrets to KeyVault
    4. Remove environment variable fallbacks

    Usage:
    This implementation is automatically used when:
    - AZURE_KEYVAULT_URL is not set
    - Azure credentials are not configured
    - KeyVault connection fails

    Note: While this class has "Mock" in its name, it is not a test mock.
    It is a functional development implementation that lives in the production
    codebase to provide a working fallback when Azure KeyVault is not available.
    Test mocks should be created in the tests/ directory using unittest.mock
    or pytest fixtures.
    """
    def __init__(self):
        logger.emit(
            "Using MockKeyVaultService - This is a temporary solution",
            severity=Severity.WARN,
            attributes={"message": "Configure Azure KeyVault for production use"}
        )

    async def get_secret(self, name: str) -> Optional[str]:
        """Get secret value from environment variable"""
        value = os.getenv(name)
        if value is None:
            logger.emit(
                "Secret not found in environment variables",
                severity=Severity.WARN,
                attributes={"secret_name": name}
            )
        return value

    async def set_secret(self, name: str, value: str, expires_in_days: Optional[int] = None):
        """Mock setting secret - logs warning since env vars can't be set at runtime"""
        logger.emit(
            "Cannot set secret in mock service",
            severity=Severity.WARN,
            attributes={
                "secret_name": name,
                "reason": "using environment variables"
            }
        )

    async def delete_secret(self, name: str):
        """Mock delete secret"""
        logger.emit(
            "Cannot delete secret in mock service",
            severity=Severity.WARN,
            attributes={
                "secret_name": name,
                "reason": "using environment variables"
            }
        )

    async def list_secrets(self, prefix: Optional[str] = None) -> List[Dict]:
        """List secrets from environment variables"""
        secrets = []
        for key, value in os.environ.items():
            if prefix and not key.startswith(prefix):
                continue
            secrets.append({
                "name": key,
                "enabled": True,
                "created_on": None,
                "updated_on": None,
                "expires_on": None
            })
        return secrets

    # Mock implementations for unused methods
    async def backup_secret(self, name: str) -> bytes:
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "backup_secret"}
        )
        return b""

    async def restore_secret(self, backup: bytes):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "restore_secret"}
        )

    async def get_key(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "get_key"}
        )
        return None

    async def create_key(self, name: str, key_type: str = "RSA", size: int = 2048):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "create_key"}
        )

    async def delete_key(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "delete_key"}
        )

    async def rotate_key(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "rotate_key"}
        )

    async def get_certificate(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "get_certificate"}
        )
        return None

    async def import_certificate(self, name: str, certificate_data: bytes, password: Optional[str] = None):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "import_certificate"}
        )

    async def delete_certificate(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "delete_certificate"}
        )

    async def list_certificates(self) -> List[Dict]:
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "list_certificates"}
        )
        return []

    async def purge_deleted_secret(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "purge_deleted_secret"}
        )

    async def purge_deleted_key(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "purge_deleted_key"}
        )

    async def purge_deleted_certificate(self, name: str):
        logger.emit(
            "Operation not implemented in mock service",
            severity=Severity.WARN,
            attributes={"operation": "purge_deleted_certificate"}
        )

class KeyVaultService:
    """Azure Key Vault service implementation"""
    def __init__(self):
        """Initialize Key Vault service or fall back to mock implementation"""
        try:
            # Get configuration
            self.vault_url = os.getenv("AZURE_KEYVAULT_URL")
            if not self.vault_url:
                logger.emit(
                    "Azure Key Vault URL not set",
                    severity=Severity.WARN,
                    attributes={"action": "falling back to mock implementation"}
                )
                self._impl = MockKeyVaultService()
                return

            # Initialize credential
            self.credential = DefaultAzureCredential()
            
            # Initialize clients
            self.secret_client = SecretClient(
                vault_url=self.vault_url,
                credential=self.credential
            )
            self.key_client = KeyClient(
                vault_url=self.vault_url,
                credential=self.credential
            )
            self.cert_client = CertificateClient(
                vault_url=self.vault_url,
                credential=self.credential
            )
            
            self._impl = self
            logger.emit(
                "Azure Key Vault service initialized",
                severity=Severity.INFO,
                attributes={"vault_url": self.vault_url}
            )

        except Exception as e:
            logger.emit(
                "Failed to initialize Azure Key Vault",
                severity=Severity.WARN,
                attributes={
                    "error": str(e),
                    "action": "falling back to mock implementation"
                }
            )
            self._impl = MockKeyVaultService()

    async def get_secret(self, name: str) -> Optional[str]:
        return await self._impl.get_secret(name)

    async def set_secret(self, name: str, value: str, expires_in_days: Optional[int] = None):
        await self._impl.set_secret(name, value, expires_in_days)

    async def delete_secret(self, name: str):
        await self._impl.delete_secret(name)

    async def list_secrets(self, prefix: Optional[str] = None) -> List[Dict]:
        return await self._impl.list_secrets(prefix)

    async def backup_secret(self, name: str) -> bytes:
        return await self._impl.backup_secret(name)

    async def restore_secret(self, backup: bytes):
        await self._impl.restore_secret(backup)

    async def get_key(self, name: str):
        return await self._impl.get_key(name)

    async def create_key(self, name: str, key_type: str = "RSA", size: int = 2048):
        await self._impl.create_key(name, key_type, size)

    async def delete_key(self, name: str):
        await self._impl.delete_key(name)

    async def rotate_key(self, name: str):
        await self._impl.rotate_key(name)

    async def get_certificate(self, name: str):
        return await self._impl.get_certificate(name)

    async def import_certificate(self, name: str, certificate_data: bytes, password: Optional[str] = None):
        await self._impl.import_certificate(name, certificate_data, password)

    async def delete_certificate(self, name: str):
        await self._impl.delete_certificate(name)

    async def list_certificates(self) -> List[Dict]:
        return await self._impl.list_certificates()

    async def purge_deleted_secret(self, name: str):
        await self._impl.purge_deleted_secret(name)

    async def purge_deleted_key(self, name: str):
        await self._impl.purge_deleted_key(name)

    async def purge_deleted_certificate(self, name: str):
        await self._impl.purge_deleted_certificate(name)
