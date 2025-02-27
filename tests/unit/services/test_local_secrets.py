"""Tests for local secrets store."""

import os
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from backend.src.services.local_secrets import LocalSecretsStore
from backend.src.utils.exceptions import KeyVaultError

@pytest.fixture
def secrets_dir(tmp_path):
    """Create temporary secrets directory."""
    return tmp_path / "secrets"

@pytest.fixture
def store(secrets_dir):
    """Create local secrets store."""
    return LocalSecretsStore(str(secrets_dir))

def test_init_creates_directory(secrets_dir):
    """Test directory creation on initialization."""
    assert not secrets_dir.exists()
    store = LocalSecretsStore(str(secrets_dir))
    assert secrets_dir.exists()
    assert (secrets_dir / "secrets.json").exists()

def test_set_get_secret(store):
    """Test setting and getting a secret."""
    store.set_secret("test-secret", "test-value")
    assert store.get_secret("test-secret") == "test-value"

def test_get_nonexistent_secret(store):
    """Test getting a nonexistent secret."""
    assert store.get_secret("nonexistent") is None

def test_delete_secret(store):
    """Test deleting a secret."""
    store.set_secret("test-secret", "test-value")
    assert store.get_secret("test-secret") == "test-value"
    
    store.delete_secret("test-secret")
    assert store.get_secret("test-secret") is None

def test_delete_nonexistent_secret(store):
    """Test deleting a nonexistent secret."""
    store.delete_secret("nonexistent")  # Should not raise

def test_secret_expiration(store):
    """Test secret expiration."""
    # Set secret that expires in 1 second
    store.set_secret(
        "test-secret",
        "test-value",
        expires_on=datetime.utcnow() + timedelta(seconds=1)
    )
    assert store.get_secret("test-secret") == "test-value"
    
    # Wait for expiration
    import time
    time.sleep(1.1)
    
    # Secret should be gone
    assert store.get_secret("test-secret") is None

def test_secret_metadata(store):
    """Test secret metadata."""
    content_type = "application/json"
    store.set_secret(
        "test-secret",
        "test-value",
        content_type=content_type,
        enabled=True
    )
    
    # Check metadata in file
    with open(store.secrets_file, "r") as f:
        data = json.load(f)
    
    assert "test-secret" in data
    assert data["test-secret"]["value"] == "test-value"
    assert data["test-secret"]["content_type"] == content_type
    assert data["test-secret"]["enabled"] is True
    assert "created_on" in data["test-secret"]
    assert "updated_on" in data["test-secret"]

def test_backup_on_update(store):
    """Test backup creation on update."""
    # Set initial secret
    store.set_secret("test-secret", "initial-value")
    
    # Update secret
    store.set_secret("test-secret", "new-value")
    
    # Check for backup file
    backup_files = list(store.secrets_path.glob("secrets.*.bak"))
    assert len(backup_files) == 1
    
    # Check backup content
    with open(backup_files[0], "r") as f:
        data = json.load(f)
    assert data["test-secret"]["value"] == "initial-value"

def test_invalid_directory(tmp_path):
    """Test initialization with invalid directory."""
    # Create a file where the directory should be
    invalid_path = tmp_path / "invalid"
    invalid_path.write_text("")
    
    with pytest.raises(KeyVaultError) as exc:
        LocalSecretsStore(str(invalid_path))
    assert "Failed to load secrets from local store" in str(exc.value)

def test_file_permissions(secrets_dir):
    """Test file permissions handling."""
    store = LocalSecretsStore(str(secrets_dir))
    
    # Make secrets file read-only
    os.chmod(store.secrets_file, 0o444)
    
    with pytest.raises(KeyVaultError) as exc:
        store.set_secret("test-secret", "test-value")
    assert "Failed to save secrets to local store" in str(exc.value)

def test_concurrent_access(store):
    """Test concurrent access handling."""
    import threading
    import random
    
    def worker():
        """Worker thread function."""
        for _ in range(10):
            name = f"secret-{random.randint(1, 100)}"
            try:
                store.set_secret(name, "test-value")
                value = store.get_secret(name)
                if value:
                    store.delete_secret(name)
            except KeyVaultError:
                pass  # Ignore expected concurrent access errors
    
    # Start multiple threads
    threads = [
        threading.Thread(target=worker)
        for _ in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    # Verify file is still valid JSON
    with open(store.secrets_file, "r") as f:
        json.load(f)  # Should not raise
