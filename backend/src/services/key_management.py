"""Key management service."""

import logging
import base64
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List, TypedDict, cast
from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.models import KeyType, KeyRotationLifetimeAction, KeyProperties
from azure.core.exceptions import ResourceNotFoundError as AzureResourceNotFoundError
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import KeyManagementError, KeyVaultError, TranscriboError
from ..types import ServiceConfig, ErrorContext, JSONValue
from .base import BaseService
from ..utils.metrics import (
    KEY_OPERATIONS,
    KEY_ERRORS,
    KEY_ROTATION_TIME,
    track_key_operation,
    track_key_error,
    track_key_rotation
)

class KeyMetadata(TypedDict, total=False):
    """Type definition for key metadata."""
    purpose: str
    owner: str
    expiry: str
    algorithm: str
    key_length: int
    custom_data: Dict[str, JSONValue]

class KeyInfo(TypedDict):
    """Type definition for key information."""
    key_id: str
    key_type: str
    created_at: str
    metadata: KeyMetadata
    version: str
    enabled: bool
    previous_version: Optional[str]

class KeyManagementService(BaseService):
    """Service for managing encryption keys."""

    def __init__(
        self,
        settings: ServiceConfig,
        key_vault_client: Optional[KeyClient] = None
    ) -> None:
        """Initialize key management service.
        
        Args:
            settings: Service configuration
            key_vault_client: Optional Azure Key Vault client
        """
        super().__init__(settings)
        self.key_vault_client: Optional[KeyClient] = key_vault_client
        self.key_cache: Dict[str, KeyInfo] = {}
        self.key_rotation_interval: int = 86400  # 24 hours
        self.max_key_age: int = 2592000  # 30 days
        self.min_key_length: int = 32

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize key management settings
            self.key_rotation_interval = int(self.settings.get('key_rotation_interval', 86400))
            self.max_key_age = int(self.settings.get('max_key_age', 2592000))
            self.min_key_length = int(self.settings.get('min_key_length', 32))

            log_info("Key management service initialized")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_key_management",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize key management service: {str(e)}")
            raise TranscriboError(
                "Failed to initialize key management service",
                details=error_context
            )

    async def _cleanup_impl(self) -> None:
        """Clean up service implementation."""
        try:
            self.key_cache.clear()
            log_info("Key management service cleaned up")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "cleanup_key_management",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error during key management service cleanup: {str(e)}")
            raise TranscriboError(
                "Failed to clean up key management service",
                details=error_context
            )

    async def create_key(
        self,
        key_type: str,
        metadata: Optional[KeyMetadata] = None
    ) -> KeyInfo:
        """Create a new key.
        
        Args:
            key_type: Type of key to create
            metadata: Optional key metadata
            
        Returns:
            Created key information
            
        Raises:
            KeyManagementError: If key creation fails
        """
        try:
            self._check_initialized()

            # Track operation
            KEY_OPERATIONS.labels(operation='create').inc()
            track_key_operation('create')

            # Create key
            key_data = await self._create_key(key_type, metadata)
            log_info(f"Created new {key_type} key")
            return key_data

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            error_context: ErrorContext = {
                "operation": "create_key",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "key_type": key_type
                }
            }
            log_error(f"Error creating {key_type} key: {str(e)}")
            raise KeyManagementError("Failed to create key", details=error_context)

    async def rotate_key(self, key_id: str) -> KeyInfo:
        """Rotate an existing key.
        
        Args:
            key_id: ID of key to rotate
            
        Returns:
            New key information
            
        Raises:
            KeyManagementError: If key rotation fails
        """
        start_time = logging.time()
        try:
            self._check_initialized()

            # Track operation
            KEY_OPERATIONS.labels(operation='rotate').inc()
            track_key_operation('rotate')

            # Rotate key
            new_key_data = await self._rotate_key(key_id)
            
            # Track rotation time
            duration = logging.time() - start_time
            KEY_ROTATION_TIME.observe(duration)
            track_key_rotation(duration)
            
            log_info(f"Rotated key {key_id}")
            return new_key_data

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            error_context: ErrorContext = {
                "operation": "rotate_key",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error rotating key {key_id}: {str(e)}")
            raise KeyManagementError("Failed to rotate key", details=error_context)

    async def revoke_key(self, key_id: str, reason: Optional[str] = None) -> None:
        """Revoke a key.
        
        Args:
            key_id: ID of key to revoke
            reason: Optional revocation reason
            
        Raises:
            KeyManagementError: If key revocation fails
        """
        try:
            self._check_initialized()

            # Track operation
            KEY_OPERATIONS.labels(operation='revoke').inc()
            track_key_operation('revoke')

            # Revoke key
            await self._revoke_key(key_id, reason)
            log_info(f"Revoked key {key_id}")

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            error_context: ErrorContext = {
                "operation": "revoke_key",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "reason": reason
                }
            }
            log_error(f"Error revoking key {key_id}: {str(e)}")
            raise KeyManagementError("Failed to revoke key", details=error_context)

    async def get_key_info(self, key_id: str) -> Optional[KeyInfo]:
        """Get key information.
        
        Args:
            key_id: ID of key to get info for
            
        Returns:
            Key information if found, None otherwise
            
        Raises:
            KeyManagementError: If key info retrieval fails
        """
        try:
            self._check_initialized()

            # Track operation
            KEY_OPERATIONS.labels(operation='info').inc()
            track_key_operation('info')

            # Get key info
            key_info = await self._get_key_info(key_id)
            
            if key_info:
                log_info(f"Retrieved info for key {key_id}")
                return key_info
            
            log_warning(f"Key {key_id} not found")
            return None

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            error_context: ErrorContext = {
                "operation": "get_key_info",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error getting info for key {key_id}: {str(e)}")
            raise KeyManagementError("Failed to get key info", details=error_context)

    async def list_keys(
        self,
        key_type: Optional[str] = None
    ) -> List[KeyInfo]:
        """List keys.
        
        Args:
            key_type: Optional key type to filter by
            
        Returns:
            List of key information
            
        Raises:
            KeyManagementError: If key listing fails
        """
        try:
            self._check_initialized()

            # Track operation
            KEY_OPERATIONS.labels(operation='list').inc()
            track_key_operation('list')

            # List keys
            keys = await self._list_keys(key_type)
            log_info(f"Listed {len(keys)} keys")
            return keys

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            error_context: ErrorContext = {
                "operation": "list_keys",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "key_type": key_type
                }
            }
            log_error(f"Error listing keys: {str(e)}")
            raise KeyManagementError("Failed to list keys", details=error_context)

    async def _create_key(
        self,
        key_type: str,
        metadata: Optional[KeyMetadata] = None
    ) -> KeyInfo:
        """Create a new key.
        
        Args:
            key_type: Type of key to create
            metadata: Optional key metadata
            
        Returns:
            Created key information
            
        Raises:
            KeyManagementError: If key creation fails
        """
        try:
            if not self.key_vault_client:
                raise KeyManagementError("Key vault client not initialized")

            # Generate a unique key name
            key_name = f"{key_type}_{uuid.uuid4().hex}"
            
            # Create key in Azure Key Vault
            key = await self.key_vault_client.create_key(
                name=key_name,
                key_type=KeyType.RSA,
                size=2048,
                tags={
                    'type': key_type,
                    'created_at': datetime.utcnow().isoformat(),
                    'metadata': json.dumps(metadata or {})
                }
            )
            
            # Store key info in cache
            key_info: KeyInfo = {
                'key_id': key.id,
                'key_type': key_type,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': metadata or {},
                'version': key.properties.version,
                'enabled': True,
                'previous_version': None
            }
            self.key_cache[key.id] = key_info
            
            return key_info
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_key_internal",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "key_type": key_type
                }
            }
            log_error(f"Error creating key: {str(e)}")
            raise KeyManagementError("Failed to create key", details=error_context)

    async def _rotate_key(self, key_id: str) -> KeyInfo:
        """Rotate a key.
        
        Args:
            key_id: ID of key to rotate
            
        Returns:
            New key information
            
        Raises:
            KeyManagementError: If key rotation fails
        """
        try:
            if not self.key_vault_client:
                raise KeyManagementError("Key vault client not initialized")

            # Get current key info
            current_key = await self._get_key_info(key_id)
            if not current_key:
                raise KeyManagementError(f"Key not found: {key_id}")
            
            # Create new key version
            key = await self.key_vault_client.rotate_key(
                name=key_id,
                policy={
                    'lifetimeActions': [
                        {
                            'trigger': {'timeAfterCreate': str(self.key_rotation_interval)},
                            'action': {'type': 'rotate'}
                        }
                    ]
                }
            )
            
            # Update cache with new version
            new_key_info: KeyInfo = {
                'key_id': key.id,
                'key_type': current_key['key_type'],
                'created_at': datetime.utcnow().isoformat(),
                'metadata': current_key['metadata'],
                'version': key.properties.version,
                'enabled': True,
                'previous_version': current_key['version']
            }
            self.key_cache[key.id] = new_key_info
            
            return new_key_info
            
        except AzureResourceNotFoundError:
            raise KeyManagementError(f"Key not found: {key_id}")
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "rotate_key_internal",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error rotating key: {str(e)}")
            raise KeyManagementError("Failed to rotate key", details=error_context)

    async def _revoke_key(self, key_id: str, reason: Optional[str] = None) -> None:
        """Revoke a key.
        
        Args:
            key_id: ID of key to revoke
            reason: Optional revocation reason
            
        Raises:
            KeyManagementError: If key revocation fails
        """
        try:
            if not self.key_vault_client:
                raise KeyManagementError("Key vault client not initialized")

            # Update key attributes to mark as revoked
            await self.key_vault_client.update_key_properties(
                name=key_id,
                enabled=False,
                tags={
                    'revoked': 'true',
                    'revoked_at': datetime.utcnow().isoformat(),
                    'revocation_reason': reason or 'No reason provided'
                }
            )
            
            # Remove from cache
            self.key_cache.pop(key_id, None)
            
        except AzureResourceNotFoundError:
            raise KeyManagementError(f"Key not found: {key_id}")
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "revoke_key_internal",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "reason": reason
                }
            }
            log_error(f"Error revoking key: {str(e)}")
            raise KeyManagementError("Failed to revoke key", details=error_context)

    async def _get_key_info(self, key_id: str) -> Optional[KeyInfo]:
        """Get key information.
        
        Args:
            key_id: ID of key to get info for
            
        Returns:
            Key information if found, None otherwise
            
        Raises:
            KeyManagementError: If key info retrieval fails
        """
        try:
            if not self.key_vault_client:
                raise KeyManagementError("Key vault client not initialized")

            # Check cache first
            if key_id in self.key_cache:
                return self.key_cache[key_id]
            
            # Get key from Azure Key Vault
            key = await self.key_vault_client.get_key(key_id)
            
            # Extract metadata from tags
            metadata = cast(
                KeyMetadata,
                json.loads(key.properties.tags.get('metadata', '{}'))
            )
            
            # Create key info
            key_info: KeyInfo = {
                'key_id': key.id,
                'key_type': key.properties.tags.get('type', 'unknown'),
                'created_at': key.properties.tags.get('created_at', datetime.utcnow().isoformat()),
                'metadata': metadata,
                'version': key.properties.version,
                'enabled': key.properties.enabled,
                'previous_version': None
            }
            
            # Update cache
            self.key_cache[key.id] = key_info
            
            return key_info
            
        except AzureResourceNotFoundError:
            return None
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "get_key_info_internal",
                "resource_id": key_id,
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error getting key info: {str(e)}")
            raise KeyManagementError("Failed to get key info", details=error_context)

    async def _list_keys(self, key_type: Optional[str] = None) -> List[KeyInfo]:
        """List keys.
        
        Args:
            key_type: Optional key type to filter by
            
        Returns:
            List of key information
            
        Raises:
            KeyManagementError: If key listing fails
        """
        try:
            if not self.key_vault_client:
                raise KeyManagementError("Key vault client not initialized")

            keys: List[KeyInfo] = []
            async for key in self.key_vault_client.list_properties_of_keys():
                # Skip if key type doesn't match filter
                if key_type and key.tags.get('type') != key_type:
                    continue
                
                # Get full key info
                key_info = await self._get_key_info(key.id)
                if key_info:
                    keys.append(key_info)
            
            return keys
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "list_keys_internal",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "key_type": key_type
                }
            }
            log_error(f"Error listing keys: {str(e)}")
            raise KeyManagementError("Failed to list keys", details=error_context)
