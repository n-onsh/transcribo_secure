"""Unit tests for authentication."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from jwt import PyJWTError
from fastapi import HTTPException, Request
from src.middleware.auth import AuthMiddleware, AuthMode
from src.utils.token_validation import TokenValidator
from src.utils.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConfigurationError
)

@pytest.fixture
def mock_request():
    """Create mock request."""
    request = Mock()
    request.headers = {}
    request.url = Mock()
    request.url.path = "/api/test"
    request.state = Mock()
    return request

@pytest.fixture
def mock_token_validator():
    """Create mock token validator."""
    validator = Mock()
    validator.validate_token = AsyncMock()
    validator.get_user_info = Mock()
    return validator

@pytest.fixture
def mock_user_service():
    """Create mock user service."""
    service = Mock()
    service.validate_token = AsyncMock()
    service.create_access_token = AsyncMock()
    return service

@pytest.fixture
def auth_middleware(mock_token_validator, mock_user_service):
    """Create auth middleware with mocked dependencies."""
    middleware = AuthMiddleware({})
    middleware.token_validator = mock_token_validator
    middleware.user_service = mock_user_service
    return middleware

@pytest.mark.asyncio
async def test_auth_middleware_public_endpoint(auth_middleware, mock_request):
    """Test public endpoint bypass."""
    # Setup
    mock_request.url.path = "/health"
    
    async def call_next(request):
        return "response"
    
    # Test
    result = await auth_middleware(mock_request, call_next)
    
    # Verify
    assert result == "response"
    assert not hasattr(mock_request.state, "auth")

@pytest.mark.asyncio
async def test_auth_middleware_missing_token(auth_middleware, mock_request):
    """Test missing token handling."""
    # Setup
    async def call_next(request):
        return "response"
    
    # Test
    with pytest.raises(HTTPException) as excinfo:
        await auth_middleware(mock_request, call_next)
        
    # Verify
    assert excinfo.value.status_code == 401
    assert "Missing authorization token" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_auth_middleware_invalid_token_format(auth_middleware, mock_request):
    """Test invalid token format handling."""
    # Setup
    mock_request.headers = {"Authorization": "Invalid token"}
    
    async def call_next(request):
        return "response"
    
    # Test
    with pytest.raises(HTTPException) as excinfo:
        await auth_middleware(mock_request, call_next)
        
    # Verify
    assert excinfo.value.status_code == 401
    assert "Missing authorization token" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_auth_middleware_azure_ad_success(auth_middleware, mock_request, mock_token_validator):
    """Test successful Azure AD authentication."""
    # Setup
    mock_request.headers = {"Authorization": "Bearer valid_token"}
    auth_middleware.auth_mode = AuthMode.AZURE_AD
    
    # Configure mock token validator
    mock_token_validator.validate_token.return_value = {
        "oid": "user_id",
        "name": "Test User",
        "email": "test@example.com"
    }
    mock_token_validator.get_user_info.return_value = {
        "id": "user_id",
        "name": "Test User",
        "email": "test@example.com",
        "roles": ["user"]
    }
    
    async def call_next(request):
        return "response"
    
    # Test
    result = await auth_middleware(mock_request, call_next)
    
    # Verify
    assert result == "response"
    assert hasattr(mock_request.state, "auth")
    assert mock_request.state.auth["user"]["id"] == "user_id"
    mock_token_validator.validate_token.assert_called_once_with("valid_token")

@pytest.mark.asyncio
async def test_auth_middleware_azure_ad_invalid_token(auth_middleware, mock_request, mock_token_validator):
    """Test invalid Azure AD token handling."""
    # Setup
    mock_request.headers = {"Authorization": "Bearer invalid_token"}
    auth_middleware.auth_mode = AuthMode.AZURE_AD
    mock_token_validator.validate_token.side_effect = AuthenticationError("Invalid token")
    
    async def call_next(request):
        return "response"
    
    # Test
    with pytest.raises(HTTPException) as excinfo:
        await auth_middleware(mock_request, call_next)
        
    # Verify
    assert excinfo.value.status_code == 401
    assert "Invalid token" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_auth_middleware_jwt_success(auth_middleware, mock_request, mock_user_service):
    """Test successful JWT authentication."""
    # Setup
    mock_request.headers = {"Authorization": "Bearer valid_token"}
    auth_middleware.auth_mode = AuthMode.JWT
    
    # Configure mock user service
    mock_user = Mock()
    mock_user.to_dict.return_value = {
        "id": "user_id",
        "username": "test_user",
        "email": "test@example.com",
        "roles": ["user"]
    }
    mock_user_service.validate_token.return_value = mock_user
    
    async def call_next(request):
        return "response"
    
    # Test
    result = await auth_middleware(mock_request, call_next)
    
    # Verify
    assert result == "response"
    assert hasattr(mock_request.state, "auth")
    assert mock_request.state.auth["user"]["id"] == "user_id"
    mock_user_service.validate_token.assert_called_once_with("valid_token")

@pytest.mark.asyncio
async def test_auth_middleware_jwt_invalid_token(auth_middleware, mock_request, mock_user_service):
    """Test invalid JWT token handling."""
    # Setup
    mock_request.headers = {"Authorization": "Bearer invalid_token"}
    auth_middleware.auth_mode = AuthMode.JWT
    mock_user_service.validate_token.return_value = None
    
    async def call_next(request):
        return "response"
    
    # Test
    with pytest.raises(HTTPException) as excinfo:
        await auth_middleware(mock_request, call_next)
        
    # Verify
    assert excinfo.value.status_code == 401
    assert "Invalid authorization token" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_token_validator_initialization():
    """Test token validator initialization."""
    # Setup
    with patch.dict('os.environ', {
        'AZURE_TENANT_ID': 'test_tenant',
        'AZURE_CLIENT_ID': 'test_client'
    }):
        # Test
        validator = TokenValidator()
        
        # Verify
        assert validator.tenant_id == 'test_tenant'
        assert validator.client_id == 'test_client'
        assert validator.jwks is None
        assert validator.jwks_uri is None

@pytest.mark.asyncio
async def test_token_validator_missing_config():
    """Test token validator initialization with missing config."""
    # Setup
    with patch.dict('os.environ', {}, clear=True):
        # Test
        with pytest.raises(ConfigurationError) as excinfo:
            TokenValidator()
            
        # Verify
        assert "Missing required Azure AD configuration" in str(excinfo.value)

@pytest.mark.asyncio
async def test_token_validator_validate_token_success():
    """Test successful token validation."""
    # Setup
    validator = TokenValidator()
    validator.jwks = {
        "keys": [{
            "kid": "test_kid",
            "kty": "RSA",
            "n": "test_n",
            "e": "test_e"
        }]
    }
    
    with patch('jwt.decode') as mock_decode:
        mock_decode.return_value = {
            "iss": f"https://login.microsoftonline.com/{validator.tenant_id}/v2.0",
            "sub": "user_id",
            "oid": "user_id",
            "name": "Test User",
            "exp": datetime.utcnow() + timedelta(hours=1)
        }
        
        # Test
        result = validator.validate_token("valid_token")
        
        # Verify
        assert result["sub"] == "user_id"
        assert result["oid"] == "user_id"
        mock_decode.assert_called_once()

@pytest.mark.asyncio
async def test_token_validator_validate_token_invalid():
    """Test invalid token validation."""
    # Setup
    validator = TokenValidator()
    validator.jwks = {
        "keys": [{
            "kid": "test_kid",
            "kty": "RSA",
            "n": "test_n",
            "e": "test_e"
        }]
    }
    
    with patch('jwt.decode') as mock_decode:
        mock_decode.side_effect = PyJWTError("Invalid token")
        
        # Test
        with pytest.raises(AuthenticationError) as excinfo:
            validator.validate_token("invalid_token")
            
        # Verify
        assert "Invalid token" in str(excinfo.value)

@pytest.mark.asyncio
async def test_token_validator_get_user_info():
    """Test user info extraction from token."""
    # Setup
    validator = TokenValidator()
    token_data = {
        "oid": "user_id",
        "name": "Test User",
        "email": "test@example.com",
        "roles": ["user"],
        "groups": ["group1"]
    }
    
    # Test
    result = validator.get_user_info(token_data)
    
    # Verify
    assert result["id"] == "user_id"
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    assert result["roles"] == ["user"]
    assert result["groups"] == ["group1"]

@pytest.mark.asyncio
async def test_token_validator_get_user_info_missing_id():
    """Test user info extraction with missing ID."""
    # Setup
    validator = TokenValidator()
    token_data = {
        "name": "Test User",
        "email": "test@example.com"
    }
    
    # Test
    with pytest.raises(AuthenticationError) as excinfo:
        validator.get_user_info(token_data)
        
    # Verify
    assert "Missing user ID in token" in str(excinfo.value)
