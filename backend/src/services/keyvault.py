import os
import logging
from typing import Optional, Dict, List
from azure.keyvault.secrets import SecretClient
from azure.keyvault.keys import KeyClient
from azure.keyvault.certificates import CertificateClient
from azure.identity import DefaultAzureCredential
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class KeyVaultService:
    def __init__(self):
        """Initialize Key Vault service"""
        # Get configuration
        self.vault_url = os.getenv("AZURE_KEYVAULT_URL")
        if not self.vault_url:
            raise ValueError("AZURE_KEYVAULT_URL environment variable not set")
        
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
        
        logger.info("Key Vault service initialized")

    async def get_secret(self, name: str) -> Optional[str]:
        """Get secret value"""
        try:
            secret = self.secret_client.get_secret(name)
            return secret.value
            
        except Exception as e:
            logger.error(f"Failed to get secret {name}: {str(e)}")
            return None

    async def set_secret(self, name: str, value: str, expires_in_days: Optional[int] = None):
        """Set secret value"""
        try:
            # Set expiry if specified
            expires_on = None
            if expires_in_days:
                expires_on = datetime.utcnow() + timedelta(days=expires_in_days)
            
            # Set secret
            self.secret_client.set_secret(
                name,
                value,
                expires_on=expires_on
            )
            
            logger.info(f"Set secret {name}")
            
        except Exception as e:
            logger.error(f"Failed to set secret {name}: {str(e)}")
            raise

    async def delete_secret(self, name: str):
        """Delete secret"""
        try:
            self.secret_client.begin_delete_secret(name).wait()
            logger.info(f"Deleted secret {name}")
            
        except Exception as e:
            logger.error(f"Failed to delete secret {name}: {str(e)}")
            raise

    async def list_secrets(self, prefix: Optional[str] = None) -> List[Dict]:
        """List secrets"""
        try:
            secrets = []
            for secret in self.secret_client.list_properties_of_secrets():
                # Filter by prefix if specified
                if prefix and not secret.name.startswith(prefix):
                    continue
                    
                secrets.append({
                    "name": secret.name,
                    "enabled": secret.enabled,
                    "created_on": secret.created_on,
                    "updated_on": secret.updated_on,
                    "expires_on": secret.expires_on
                })
            
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets: {str(e)}")
            raise

    async def backup_secret(self, name: str) -> bytes:
        """Backup secret"""
        try:
            backup = self.secret_client.backup_secret(name)
            logger.info(f"Backed up secret {name}")
            return backup
            
        except Exception as e:
            logger.error(f"Failed to backup secret {name}: {str(e)}")
            raise

    async def restore_secret(self, backup: bytes):
        """Restore secret from backup"""
        try:
            self.secret_client.restore_secret_backup(backup)
            logger.info("Restored secret from backup")
            
        except Exception as e:
            logger.error(f"Failed to restore secret: {str(e)}")
            raise

    async def get_key(self, name: str):
        """Get key"""
        try:
            return self.key_client.get_key(name)
            
        except Exception as e:
            logger.error(f"Failed to get key {name}: {str(e)}")
            raise

    async def create_key(self, name: str, key_type: str = "RSA", size: int = 2048):
        """Create key"""
        try:
            self.key_client.create_rsa_key(
                name=name,
                key_size=size,
                enabled=True
            )
            logger.info(f"Created key {name}")
            
        except Exception as e:
            logger.error(f"Failed to create key {name}: {str(e)}")
            raise

    async def delete_key(self, name: str):
        """Delete key"""
        try:
            self.key_client.begin_delete_key(name).wait()
            logger.info(f"Deleted key {name}")
            
        except Exception as e:
            logger.error(f"Failed to delete key {name}: {str(e)}")
            raise

    async def rotate_key(self, name: str):
        """Rotate key"""
        try:
            # Create new version
            await self.create_key(name)
            logger.info(f"Rotated key {name}")
            
        except Exception as e:
            logger.error(f"Failed to rotate key {name}: {str(e)}")
            raise

    async def get_certificate(self, name: str):
        """Get certificate"""
        try:
            return self.cert_client.get_certificate(name)
            
        except Exception as e:
            logger.error(f"Failed to get certificate {name}: {str(e)}")
            raise

    async def import_certificate(
        self,
        name: str,
        certificate_data: bytes,
        password: Optional[str] = None
    ):
        """Import certificate"""
        try:
            self.cert_client.import_certificate(
                name,
                certificate_data,
                password=password
            )
            logger.info(f"Imported certificate {name}")
            
        except Exception as e:
            logger.error(f"Failed to import certificate {name}: {str(e)}")
            raise

    async def delete_certificate(self, name: str):
        """Delete certificate"""
        try:
            self.cert_client.begin_delete_certificate(name).wait()
            logger.info(f"Deleted certificate {name}")
            
        except Exception as e:
            logger.error(f"Failed to delete certificate {name}: {str(e)}")
            raise

    async def list_certificates(self) -> List[Dict]:
        """List certificates"""
        try:
            certificates = []
            for cert in self.cert_client.list_properties_of_certificates():
                certificates.append({
                    "name": cert.name,
                    "enabled": cert.enabled,
                    "created_on": cert.created_on,
                    "updated_on": cert.updated_on,
                    "expires_on": cert.expires_on
                })
            
            return certificates
            
        except Exception as e:
            logger.error(f"Failed to list certificates: {str(e)}")
            raise

    async def purge_deleted_secret(self, name: str):
        """Purge deleted secret"""
        try:
            self.secret_client.purge_deleted_secret(name)
            logger.info(f"Purged deleted secret {name}")
            
        except Exception as e:
            logger.error(f"Failed to purge deleted secret {name}: {str(e)}")
            raise

    async def purge_deleted_key(self, name: str):
        """Purge deleted key"""
        try:
            self.key_client.purge_deleted_key(name)
            logger.info(f"Purged deleted key {name}")
            
        except Exception as e:
            logger.error(f"Failed to purge deleted key {name}: {str(e)}")
            raise

    async def purge_deleted_certificate(self, name: str):
        """Purge deleted certificate"""
        try:
            self.cert_client.purge_deleted_certificate(name)
            logger.info(f"Purged deleted certificate {name}")
            
        except Exception as e:
            logger.error(f"Failed to purge deleted certificate {name}: {str(e)}")
            raise
