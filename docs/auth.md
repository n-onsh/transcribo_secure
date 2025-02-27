# Authentication Guide

This document describes the authentication system in Transcribo.

## Overview

Transcribo supports two authentication modes:
1. Azure AD (default) - For production use with Azure Active Directory
2. JWT - For development and testing

The authentication mode and settings are configured through environment variables and managed by the configuration system.

## Configuration

Authentication settings are defined in the `.env` file:

```env
# Authentication mode (azure_ad or jwt)
AUTH_MODE=azure_ad

# Azure AD settings (required if AUTH_MODE=azure_ad)
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id

# JWT settings (required if AUTH_MODE=jwt)
JWT_SECRET_KEY=your_secure_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
```

## Azure AD Authentication

When using Azure AD authentication:

1. Configure Azure AD settings in your `.env` file:
   ```env
   AUTH_MODE=azure_ad
   AZURE_TENANT_ID=your_tenant_id
   AZURE_CLIENT_ID=your_client_id
   ```

2. The system will validate tokens using Azure AD's OpenID configuration:
   - Validates token signature using JWKS
   - Verifies token claims (issuer, audience, expiration)
   - Extracts user information from claims

3. User roles and permissions are derived from Azure AD groups and roles

## JWT Authentication

JWT authentication is intended for development and testing:

1. Configure JWT settings in your `.env` file:
   ```env
   AUTH_MODE=jwt
   JWT_SECRET_KEY=your_secure_jwt_secret_here
   JWT_ALGORITHM=HS256
   JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
   ```

2. Use the `/auth/login` endpoint to get a token:
   ```http
   POST /api/v1/auth/login
   Content-Type: application/json

   {
     "username": "test_user",
     "password": "test_password"
   }
   ```

3. The response includes an access token:
   ```json
   {
     "access_token": "eyJ0eXAi...",
     "token_type": "bearer",
     "expires_in": 3600
   }
   ```

Note: JWT authentication is only available in development mode.

## Using Authentication

1. Include the token in requests:
   ```http
   GET /api/v1/protected-endpoint
   Authorization: Bearer your_token_here
   ```

2. The auth middleware will:
   - Validate the token
   - Extract user information
   - Add auth context to the request

3. Access auth context in routes:
   ```python
   @router.get("/me")
   async def get_current_user(request: Request):
       auth_context = request.state.auth
       user = auth_context["user"]
       return user
   ```

## Auth Endpoints

- `GET /api/v1/auth/validate` - Validate token and return user info
- `GET /api/v1/auth/me` - Get current user info
- `GET /api/v1/auth/roles` - Get user roles
- `GET /api/v1/auth/has-role/{role}` - Check if user has specific role
- `POST /api/v1/auth/login` - Login (JWT mode only, development)

## User Information

The user info object contains:

```json
{
  "id": "user_id",
  "email": "user@example.com",
  "name": "User Name",
  "roles": ["role1", "role2"],
  "scopes": ["scope1", "scope2"],
  "type": "azure_ad"
}
```

## Error Handling

Authentication errors return appropriate HTTP status codes:

- 401 Unauthorized - Invalid or missing token
- 403 Forbidden - Valid token but insufficient permissions
- 500 Internal Server Error - Server-side authentication error

Error responses include details:

```json
{
  "detail": "Authentication failed: Token expired"
}
```

## Development Setup

1. Create a `.env` file based on `.env.example`
2. Choose authentication mode:
   - For Azure AD: Configure Azure AD application
   - For JWT: Use development mode settings

3. Start the application:
   ```bash
   docker-compose up
   ```

## Security Considerations

1. Always use HTTPS in production
2. Keep secrets secure:
   - Never commit `.env` file
   - Use secure secret management in production
   - Rotate secrets regularly

3. Token security:
   - Short expiration times
   - Validate all claims
   - Use secure algorithms

4. Role-based access:
   - Assign minimal required roles
   - Validate roles for sensitive operations
   - Log access attempts
