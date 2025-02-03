# tests/test_backend_config.py
import os
import pytest
from backend_api.src.config import get_settings  # Absolute import

def test_backend_settings_loading(monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "test_postgres")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("POSTGRES_DB", "test_db")
    monkeypatch.setenv("POSTGRES_USER", "test_user")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test_password")
    monkeypatch.setenv("MINIO_HOST", "test_minio")
    monkeypatch.setenv("MINIO_PORT", "9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test_minio_user")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test_minio_password")
    monkeypatch.setenv("AZURE_KEYVAULT_URL", "https://test-keyvault.vault.azure.net/")
    monkeypatch.setenv("AZURE_TENANT_ID", "test_tenant")
    monkeypatch.setenv("AZURE_CLIENT_ID", "test_client")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test_secret")
    monkeypatch.setenv("MAX_UPLOAD_SIZE", "1000000")
    
    settings = get_settings()
    
    assert settings.POSTGRES_HOST == "test_postgres"
    assert settings.POSTGRES_PORT == "5432"
    assert settings.POSTGRES_DB == "test_db"
    assert settings.POSTGRES_USER == "test_user"
    assert settings.POSTGRES_PASSWORD == "test_password"
    assert settings.MINIO_HOST == "test_minio"
    assert settings.MINIO_PORT == "9000"
    assert settings.MINIO_ACCESS_KEY == "test_minio_user"
    assert settings.MINIO_SECRET_KEY == "test_minio_password"
    assert settings.AZURE_KEYVAULT_URL == "https://test-keyvault.vault.azure.net/"
    assert settings.AZURE_TENANT_ID == "test_tenant"
    assert settings.AZURE_CLIENT_ID == "test_client"
    assert settings.AZURE_CLIENT_SECRET == "test_secret"
    assert settings.MAX_UPLOAD_SIZE == 1000000
