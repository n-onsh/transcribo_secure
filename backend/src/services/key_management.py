"""Key management service."""

import logging
import base64
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from azure.keyvault.keys import KeyClient
from azure.keyvault.keys.models import KeyType, KeyRotationLifetimeAction
from azure.core.exceptions import ResourceNotFoundError as AzureResourceNotFoundError
from ..utils.logging import log_info, log_error, log_warning
from ..utils.exceptions import KeyManagementError, KeyVaultError
from ..utils.metrics import (
    KEY_OPERATIONS,
    KEY_ERRORS,
    KEY_ROTATION_TIME,
    track_key_operation,
    track_key_error,
    track_key_rotation
)

class KeyManagementService:
    """Service for managing encryption keys."""

    def __init__(self, settings, key_vault_client: Optional[KeyClient] = None):
        """Initialize key management service."""
        self.settings = settings
        self.initialized = False
        self.key_vault_client = key_vault_client
        self.key_cache = {}

    async def initialize(self):
        """Initialize the service."""
        if self.initialized:
            return

        try:
            # Initialize key management settings
            self.key_rotation_interval = int(self.settings.get('key_rotation_interval', 86400))  # 24 hours
            self.max_key_age = int(self.settings.get('max_key_age', 2592000))  # 30 days
            self.min_key_length = int(self.settings.get('min_key_length', 32))

            self.initialized = True
            log_info("Key management service initialized")

        except Exception as e:
            log_error(f"Failed to initialize key management service: {str(e)}")
            raise

    async def cleanup(self):
        """Clean up the service."""
        try:
            self.initialized = False
            log_info("Key management service cleaned up")

        except Exception as e:
            log_error(f"Error during key management service cleanup: {str(e)}")
            raise

    async def create_key(self, key_type: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new key."""
        try:
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
            log_error(f"Error creating {key_type} key: {str(e)}")
            raise

    async def rotate_key(self, key_id: str) -> Dict:
        """Rotate an existing key."""
        start_time = logging.time()
        try:
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
            log_error(f"Error rotating key {key_id}: {str(e)}")
            raise

    async def revoke_key(self, key_id: str, reason: Optional[str] = None):
        """Revoke a key."""
        try:
            # Track operation
            KEY_OPERATIONS.labels(operation='revoke').inc()
            track_key_operation('revoke')

            # Revoke key
            await self._revoke_key(key_id, reason)
            log_info(f"Revoked key {key_id}")

        except Exception as e:
            KEY_ERRORS.inc()
            track_key_error()
            log_error(f"Error revoking key {key_id}: {str(e)}")
            raise

    async def get_key_info(self, key_id: str) -> Optional[Dict]:
        """Get key information."""
        try:
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
            log_error(f"Error getting info for key {key_id}: {str(e)}")
            raise

    async def list_keys(self, key_type: Optional[str] = None) -> List[Dict]:
        """List keys."""
        try:
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
            log_error(f"Error listing keys: {str(e)}")
            raise

    async def _create_key(self, key_type: str, metadata: Optional[Dict] = None) -> Dict:
        """Create a new key."""
        try:
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
            key_info = {
                'key_id': key.id,
                'key_type': key_type,
                'created_at': datetime.utcnow().isoformat(),
                'metadata': metadata or {},
                'version': key.properties.version
            }
            self.key_cache[key.id] = key_info
            
            return key_info
            
        except Exception as e:
            log_error(f"Error creating key: {str(e)}")
            raise KeyManagementError(f"Failed to create key: {str(e)}")

    async def _rotate_key(self, key_id: str) -> Dict:
        """Rotate a key."""
        try:
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
            new_key_info = {
                'key_id': key.id,
                'key_type': current_key['key_type'],
                'created_at': datetime.utcnow().isoformat(),
                'metadata': current_key['metadata'],
                'version': key.properties.version,
                'previous_version': current_key['version']
            }
            self.key_cache[key.id] = new_key_info
            
            return new_key_info
            
        except AzureResourceNotFoundError:
            raise KeyManagementError(f"Key not found: {key_id}")
        except Exception as e:
            log_error(f"Error rotating key: {str(e)}")
            raise KeyManagementError(f"Failed to rotate key: {str(e)}")

    async def _revoke_key(self, key_id: str, reason: Optional[str] = None):
        """Revoke a key."""
        try:
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
            log_error(f"Error revoking key: {str(e)}")
            raise KeyManagementError(f"Failed to revoke key: {str(e)}")

    async def _get_key_info(self, key_id: str) -> Optional[Dict]:
        """Get key information."""
        try:
            # Check cache first
            if key_id in self.key_cache:
                return self.key_cache[key_id]
            
            # Get key from Azure Key Vault
            key = await self.key_vault_client.get_key(key_id)
            
            # Extract metadata from tags
            metadata = json.loads(key.properties.tags.get('metadata', '{}'))
            
            # Create key info
            key_info = {
                'key_id': key.id,
                'key_type': key.properties.tags.get('type'),
                'created_at': key.properties.tags.get('created_at'),
                'metadata': metadata,
                'version': key.properties.version,
                'enabled': key.properties.enabled
            }
            
            # Update cache
            self.key_cache[key.id] = key_info
            
            return key_info
            
        except AzureResourceNotFoundError:
            return None
        except Exception as e:
            log_error(f"Error getting key info: {str(e)}")
            raise KeyManagementError(f"Failed to get key info: {str(e)}")

    async def _list_keys(self, key_type: Optional[str] = None) -> List[Dict]:
        """List keys."""
        try:
            keys = []
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
            log_error(f"Error listing keys: {str(e)}")
            raise KeyManagementError(f"Failed to list keys: {str(e)}")
