"""Azure Key Vault service."""

import asyncio
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, Any
from azure.keyvault.secrets import SecretClient
from azure.core.exceptions import (
    ResourceNotFoundError,
    ClientAuthenticationError,
    ServiceRequestError
)
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    KEY_VAULT_OPERATIONS,
    KEY_VAULT_ERRORS,
    KEY_VAULT_LATENCY,
    track_key_vault_operation,
    track_key_vault_error,
    track_key_vault_latency
)
from ..types import ErrorContext
from ..utils.exceptions import KeyVaultError, ConfigurationError
from .base import BaseService
from .local_secrets import LocalSecretsStore
from ..config import config

class KeyVaultService(BaseService):
    """Service for Azure Key Vault operations."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize service.
        
        Args:
            settings: Service settings
        """
        super().__init__(settings)
        self.config = config.storage.encryption.key_vault
        self.client: Optional[SecretClient] = None
        self.local_store: Optional[LocalSecretsStore] = None
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: Dict[str, datetime] = {}
        self.cache_enabled = self.config.cache_enabled
        self.cache_duration = timedelta(minutes=self.config.cache_duration_minutes)

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            if not self.config.enabled:
                log_info("Key Vault integration disabled")
                return

            if self.config.mode == "local":
                # Initialize local secrets store
                self.local_store = LocalSecretsStore(self.config.local_path)
                log_info("Using local secrets store", {
                    "path": self.config.local_path
                })
            else:
                # Initialize Azure Key Vault client
                if not all([
                    self.config.url,
                    self.config.tenant_id,
                    self.config.client_id,
                    self.config.client_secret
                ]):
                    raise ConfigurationError("Missing required Azure Key Vault configuration")

                # Initialize client
                from azure.identity import ClientSecretCredential
                credential = ClientSecretCredential(
                    tenant_id=self.config.tenant_id,
                    client_id=self.config.client_id,
                    client_secret=self.config.client_secret
                )
                self.client = SecretClient(vault_url=self.config.url, credential=credential)

                # Test connection
                await asyncio.to_thread(self.client.get_secret, "test-connection")
                log_info("Connected to Azure Key Vault", {
                    "url": self.config.url
                })

        except ResourceNotFoundError:
            # Test secret not found, but connection works
            log_info("Azure Key Vault connection successful")
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_key_vault",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize Key Vault service: {str(e)}")
            raise KeyVaultError(
                "Failed to initialize Key Vault service",
                details=error_context
            )

    def _get_from_cache(self, name: str) -> Optional[Any]:
        """Get value from cache if valid.
        
        Args:
            name: Secret name
            
        Returns:
            Cached value if valid, None otherwise
        """
        if not self.cache_enabled:
            return None

        if name not in self.cache or name not in self.cache_ttl:
            return None

        if datetime.utcnow() > self.cache_ttl[name]:
            # Cache expired
            del self.cache[name]
            del self.cache_ttl[name]
            return None

        return self.cache[name]

    def _add_to_cache(self, name: str, value: Any) -> None:
        """Add value to cache.
        
        Args:
            name: Secret name
            value: Secret value
        """
        if not self.cache_enabled:
            return

        self.cache[name] = value
        self.cache_ttl[name] = datetime.utcnow() + self.cache_duration

    async def get_secret(self, name: str) -> Optional[str]:
        """Get a secret.
        
        Args:
            name: Secret name
            
        Returns:
            Secret value if found, None otherwise
            
        Raises:
            KeyVaultError: If retrieval fails
        """
        try:
            # Track operation
            track_key_vault_operation('get_secret')
            start_time = datetime.utcnow()

            # Check cache first
            cached_value = self._get_from_cache(name)
            if cached_value is not None:
                log_info(f"Cache hit for secret {name}")
                return cached_value

            # Get from store
            if self.config.mode == "local":
                if not self.local_store:
                    raise KeyVaultError("Local secrets store not initialized")
                value = self.local_store.get_secret(name)
            else:
                if not self.client:
                    raise KeyVaultError("Azure Key Vault client not initialized")
                try:
                    secret = await asyncio.to_thread(self.client.get_secret, name)
                    value = secret.value
                except ResourceNotFoundError:
                    value = None

            # Add to cache if found
            if value is not None:
                self._add_to_cache(name, value)

            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            KEY_VAULT_LATENCY.observe(duration)
            track_key_vault_latency(duration)

            return value

        except Exception as e:
            # Track error
            KEY_VAULT_ERRORS.inc()
            track_key_vault_error()

            error_context: ErrorContext = {
                "operation": "get_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to get secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to get secret: {str(e)}",
                details=error_context
            )

    async def set_secret(
        self,
        name: str,
        value: str,
        content_type: Optional[str] = None,
        enabled: bool = True,
        expires_on: Optional[datetime] = None
    ) -> None:
        """Set a secret.
        
        Args:
            name: Secret name
            value: Secret value
            content_type: Optional content type
            enabled: Whether secret is enabled
            expires_on: Optional expiration time
            
        Raises:
            KeyVaultError: If operation fails
        """
        try:
            # Track operation
            track_key_vault_operation('set_secret')
            start_time = datetime.utcnow()

            # Set in store
            if self.config.mode == "local":
                if not self.local_store:
                    raise KeyVaultError("Local secrets store not initialized")
                self.local_store.set_secret(
                    name=name,
                    value=value,
                    content_type=content_type,
                    enabled=enabled,
                    expires_on=expires_on
                )
            else:
                if not self.client:
                    raise KeyVaultError("Azure Key Vault client not initialized")
                await asyncio.to_thread(
                    self.client.set_secret,
                    name=name,
                    value=value,
                    content_type=content_type,
                    enabled=enabled,
                    expires_on=expires_on
                )

            # Update cache
            self._add_to_cache(name, value)

            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            KEY_VAULT_LATENCY.observe(duration)
            track_key_vault_latency(duration)

            log_info(f"Set secret {name}")

        except Exception as e:
            # Track error
            KEY_VAULT_ERRORS.inc()
            track_key_vault_error()

            error_context: ErrorContext = {
                "operation": "set_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to set secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to set secret: {str(e)}",
                details=error_context
            )

    async def delete_secret(self, name: str) -> None:
        """Delete a secret.
        
        Args:
            name: Secret name
            
        Raises:
            KeyVaultError: If operation fails
        """
        try:
            # Track operation
            track_key_vault_operation('delete_secret')
            start_time = datetime.utcnow()

            # Remove from cache
            if name in self.cache:
                del self.cache[name]
            if name in self.cache_ttl:
                del self.cache_ttl[name]

            # Delete from store
            if self.config.mode == "local":
                if not self.local_store:
                    raise KeyVaultError("Local secrets store not initialized")
                self.local_store.delete_secret(name)
            else:
                if not self.client:
                    raise KeyVaultError("Azure Key Vault client not initialized")
                try:
                    await asyncio.to_thread(
                        self.client.begin_delete_secret,
                        name
                    )
                except ResourceNotFoundError:
                    pass

            # Track latency
            duration = (datetime.utcnow() - start_time).total_seconds()
            KEY_VAULT_LATENCY.observe(duration)
            track_key_vault_latency(duration)

            log_info(f"Deleted secret {name}")

        except Exception as e:
            # Track error
            KEY_VAULT_ERRORS.inc()
            track_key_vault_error()

            error_context: ErrorContext = {
                "operation": "delete_secret",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "secret_name": name
                }
            }
            log_error(f"Failed to delete secret {name}: {str(e)}")
            raise KeyVaultError(
                f"Failed to delete secret: {str(e)}",
                details=error_context
            )
