"""Tests for Key Vault service."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta
from azure.core.exceptions import ResourceNotFoundError

from backend.src.services.keyvault import KeyVaultService
from backend.src.services.local_secrets import LocalSecretsStore
from backend.src.utils.exceptions import KeyVaultError, ConfigurationError

@pytest.fixture
def mock_config():
    """Mock configuration."""
    return {
        "storage": {
            "encryption": {
                "key_vault": {
                    "enabled": True,
                    "mode": "local",
                    "url": None,
                    "tenant_id": None,
                    "client_id": None,
                    "client_secret": None,
                    "cache_enabled": True,
                    "cache_duration_minutes": 60,
                    "local_path": "secrets"
                }
            }
        }
    }

@pytest.fixture
def mock_local_store():
    """Mock local secrets store."""
    store = Mock(spec=LocalSecretsStore)
    store.get_secret.return_value = "test-value"
    return store

@pytest.fixture
def mock_azure_client():
    """Mock Azure Key Vault client."""
    client = Mock()
    client.get_secret.return_value = Mock(value="test-value")
    return client

@pytest.fixture
def service(mock_config):
    """Create Key Vault service."""
    with patch("backend.src.services.keyvault.config", mock_config):
        return KeyVaultService({})

@pytest.mark.asyncio
async def test_local_mode_initialization(service, mock_local_store):
    """Test initialization in local mode."""
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        assert service.local_store == mock_local_store
        assert service.client is None

@pytest.mark.asyncio
async def test_azure_mode_initialization(mock_config, mock_azure_client):
    """Test initialization in Azure mode."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure",
        "url": "https://test.vault.azure.net",
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret"
    })
    
    with patch("backend.src.services.keyvault.config", mock_config), \
         patch("backend.src.services.keyvault.ClientSecretCredential"), \
         patch("backend.src.services.keyvault.SecretClient", return_value=mock_azure_client):
        service = KeyVaultService({})
        await service.initialize()
        assert service.client == mock_azure_client
        assert service.local_store is None

@pytest.mark.asyncio
async def test_azure_mode_missing_config(mock_config):
    """Test initialization in Azure mode with missing config."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure"
    })
    
    with patch("backend.src.services.keyvault.config", mock_config):
        service = KeyVaultService({})
        with pytest.raises(ConfigurationError) as exc:
            await service.initialize()
        assert "Missing required Azure Key Vault configuration" in str(exc.value)

@pytest.mark.asyncio
async def test_get_secret_local_mode(service, mock_local_store):
    """Test getting secret in local mode."""
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        value = await service.get_secret("test-secret")
        assert value == "test-value"
        mock_local_store.get_secret.assert_called_once_with("test-secret")

@pytest.mark.asyncio
async def test_get_secret_azure_mode(mock_config, mock_azure_client):
    """Test getting secret in Azure mode."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure",
        "url": "https://test.vault.azure.net",
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret"
    })
    
    with patch("backend.src.services.keyvault.config", mock_config), \
         patch("backend.src.services.keyvault.ClientSecretCredential"), \
         patch("backend.src.services.keyvault.SecretClient", return_value=mock_azure_client):
        service = KeyVaultService({})
        await service.initialize()
        value = await service.get_secret("test-secret")
        assert value == "test-value"
        mock_azure_client.get_secret.assert_called_once_with("test-secret")

@pytest.mark.asyncio
async def test_get_secret_not_found_local(service, mock_local_store):
    """Test getting nonexistent secret in local mode."""
    mock_local_store.get_secret.return_value = None
    
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        value = await service.get_secret("nonexistent")
        assert value is None

@pytest.mark.asyncio
async def test_get_secret_not_found_azure(mock_config, mock_azure_client):
    """Test getting nonexistent secret in Azure mode."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure",
        "url": "https://test.vault.azure.net",
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret"
    })
    mock_azure_client.get_secret.side_effect = ResourceNotFoundError()
    
    with patch("backend.src.services.keyvault.config", mock_config), \
         patch("backend.src.services.keyvault.ClientSecretCredential"), \
         patch("backend.src.services.keyvault.SecretClient", return_value=mock_azure_client):
        service = KeyVaultService({})
        await service.initialize()
        value = await service.get_secret("nonexistent")
        assert value is None

@pytest.mark.asyncio
async def test_set_secret_local_mode(service, mock_local_store):
    """Test setting secret in local mode."""
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        await service.set_secret(
            "test-secret",
            "test-value",
            content_type="text/plain",
            expires_on=datetime.utcnow() + timedelta(days=1)
        )
        mock_local_store.set_secret.assert_called_once()

@pytest.mark.asyncio
async def test_set_secret_azure_mode(mock_config, mock_azure_client):
    """Test setting secret in Azure mode."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure",
        "url": "https://test.vault.azure.net",
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret"
    })
    
    with patch("backend.src.services.keyvault.config", mock_config), \
         patch("backend.src.services.keyvault.ClientSecretCredential"), \
         patch("backend.src.services.keyvault.SecretClient", return_value=mock_azure_client):
        service = KeyVaultService({})
        await service.initialize()
        await service.set_secret(
            "test-secret",
            "test-value",
            content_type="text/plain",
            expires_on=datetime.utcnow() + timedelta(days=1)
        )
        mock_azure_client.set_secret.assert_called_once()

@pytest.mark.asyncio
async def test_delete_secret_local_mode(service, mock_local_store):
    """Test deleting secret in local mode."""
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        await service.delete_secret("test-secret")
        mock_local_store.delete_secret.assert_called_once_with("test-secret")

@pytest.mark.asyncio
async def test_delete_secret_azure_mode(mock_config, mock_azure_client):
    """Test deleting secret in Azure mode."""
    mock_config["storage"]["encryption"]["key_vault"].update({
        "mode": "azure",
        "url": "https://test.vault.azure.net",
        "tenant_id": "test-tenant",
        "client_id": "test-client",
        "client_secret": "test-secret"
    })
    
    with patch("backend.src.services.keyvault.config", mock_config), \
         patch("backend.src.services.keyvault.ClientSecretCredential"), \
         patch("backend.src.services.keyvault.SecretClient", return_value=mock_azure_client):
        service = KeyVaultService({})
        await service.initialize()
        await service.delete_secret("test-secret")
        mock_azure_client.begin_delete_secret.assert_called_once_with("test-secret")

@pytest.mark.asyncio
async def test_caching(service, mock_local_store):
    """Test secret caching."""
    with patch("backend.src.services.keyvault.LocalSecretsStore", return_value=mock_local_store):
        await service.initialize()
        
        # First get should hit store
        value1 = await service.get_secret("test-secret")
        assert value1 == "test-value"
        assert mock_local_store.get_secret.call_count == 1
        
        # Second get should use cache
        value2 = await service.get_secret("test-secret")
        assert value2 == "test-value"
        assert mock_local_store.get_secret.call_count == 1
        
        # After setting, cache should be updated
        await service.set_secret("test-secret", "new-value")
        value3 = await service.get_secret("test-secret")
        assert value3 == "new-value"
        assert mock_local_store.get_secret.call_count == 1
        
        # After deleting, cache should be cleared
        await service.delete_secret("test-secret")
        mock_local_store.get_secret.return_value = None
        value4 = await service.get_secret("test-secret")
        assert value4 is None
        assert mock_local_store.get_secret.call_count == 2
