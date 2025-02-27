"""Integration tests for authentication flow."""

import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from src.main import app
from src.middleware.auth import AuthMode
from src.utils.token_validation import TokenValidator
from src.utils.exceptions import AuthenticationError

@pytest.fixture
def test_client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def mock_azure_config():
    """Mock Azure AD configuration."""
    with patch.dict('os.environ', {
        'AUTH_MODE': AuthMode.AZURE_AD,
        'AZURE_TENANT_ID': 'test_tenant',
        'AZURE_CLIENT_ID': 'test_client'
    }):
        yield

@pytest.fixture
def mock_jwt_config():
    """Mock JWT configuration."""
    with patch.dict('os.environ', {
        'AUTH_MODE': AuthMode.JWT,
        'JWT_SECRET_KEY': 'test_secret',
        'JWT_ALGORITHM': 'HS256',
        'JWT_ACCESS_TOKEN_EXPIRE_MINUTES': '60',
        'ENVIRONMENT': 'development'
    }):
        yield

@pytest.fixture
def mock_token_validator():
    """Mock token validator."""
    with patch('src.middleware.auth.TokenValidator') as mock:
        validator = mock.return_value
        validator.validate_token.return_value = {
            "iss": "https://login.microsoftonline.com/test_tenant/v2.0",
            "sub": "test_user",
            "oid": "test_user",
            "name": "Test User",
            "email": "test@example.com",
            "roles": ["user"]
        }
        validator.get_user_info.return_value = {
            "id": "test_user",
            "name": "Test User",
            "email": "test@example.com",
            "roles": ["user"]
        }
        yield validator

def test_health_check(test_client):
    """Test health check endpoint."""
    response = test_client.get("/auth/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_azure_ad_auth_flow(test_client, mock_azure_config, mock_token_validator):
    """Test Azure AD authentication flow."""
    # Test without token
    response = test_client.get("/auth/me")
    assert response.status_code == 401
    assert "Missing authorization token" in response.json()["detail"]

    # Test with invalid token
    mock_token_validator.validate_token.side_effect = AuthenticationError("Invalid token")
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    assert "Invalid token" in response.json()["detail"]

    # Test with valid token
    mock_token_validator.validate_token.side_effect = None
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test_user"
    assert data["name"] == "Test User"
    assert data["email"] == "test@example.com"
    assert data["roles"] == ["user"]
    assert data["type"] == AuthMode.AZURE_AD

@pytest.mark.asyncio
async def test_jwt_auth_flow(test_client, mock_jwt_config):
    """Test JWT authentication flow."""
    # Test login
    response = test_client.post(
        "/auth/login",
        json={"username": "test_user", "password": "password"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    access_token = data["access_token"]
    refresh_token = data["refresh_token"]

    # Test accessing protected endpoint
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test_user"
    assert data["type"] == AuthMode.JWT

    # Test token refresh
    response = test_client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] != access_token

@pytest.mark.asyncio
async def test_role_checks(test_client, mock_azure_config, mock_token_validator):
    """Test role checking endpoints."""
    # Configure mock with admin role
    mock_token_validator.get_user_info.return_value = {
        "id": "test_user",
        "name": "Test User",
        "email": "test@example.com",
        "roles": ["user", "admin"]
    }

    # Test getting roles
    response = test_client.get(
        "/auth/roles",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == ["user", "admin"]

    # Test has_role with existing role
    response = test_client.get(
        "/auth/has-role/admin",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_role"] is True

    # Test has_role with non-existent role
    response = test_client.get(
        "/auth/has-role/super_admin",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["has_role"] is False

@pytest.mark.asyncio
async def test_token_validation(test_client, mock_azure_config, mock_token_validator):
    """Test token validation endpoint."""
    # Test valid token
    response = test_client.get(
        "/auth/validate",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test_user"
    assert data["email"] == "test@example.com"
    assert data["roles"] == ["user"]
    assert data["type"] == AuthMode.AZURE_AD

    # Test expired token
    mock_token_validator.validate_token.side_effect = AuthenticationError("Token expired")
    response = test_client.get(
        "/auth/validate",
        headers={"Authorization": "Bearer expired_token"}
    )
    assert response.status_code == 401
    assert "Token expired" in response.json()["detail"]

@pytest.mark.asyncio
async def test_auth_mode_switching():
    """Test auth mode switching behavior."""
    # Test Azure AD mode
    with patch.dict('os.environ', {'AUTH_MODE': AuthMode.AZURE_AD}):
        app.dependency_overrides = {}  # Reset dependencies
        client = TestClient(app)
        response = client.post("/auth/login")
        assert response.status_code == 404
        assert "not available in current auth mode" in response.json()["detail"]

    # Test JWT mode
    with patch.dict('os.environ', {
        'AUTH_MODE': AuthMode.JWT,
        'ENVIRONMENT': 'development'
    }):
        app.dependency_overrides = {}  # Reset dependencies
        client = TestClient(app)
        response = client.post(
            "/auth/login",
            json={"username": "test_user", "password": "password"}
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_error_responses(test_client, mock_azure_config, mock_token_validator):
    """Test error response formats."""
    # Test authentication error
    mock_token_validator.validate_token.side_effect = AuthenticationError("Invalid token")
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "Invalid token" in data["detail"]

    # Test authorization error
    mock_token_validator.get_user_info.return_value = {
        "id": "test_user",
        "name": "Test User",
        "email": "test@example.com",
        "roles": []
    }
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["roles"] == []

    # Test server error
    mock_token_validator.validate_token.side_effect = Exception("Internal error")
    response = test_client.get(
        "/auth/me",
        headers={"Authorization": "Bearer valid_token"}
    )
    assert response.status_code == 500
    assert "Authentication error" in response.json()["detail"]
