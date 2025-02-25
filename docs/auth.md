# Authentication Setup

This document outlines the authentication setup for both development and production environments.

## Overview

The system uses Azure AD for authentication with different configurations for development and production environments.

## Development Setup

### Azure AD Configuration
1. Register Development App:
   ```bash
   # Using Azure CLI
   az ad app create --display-name "Transcribo-Dev" \
     --web-redirect-uris "http://localhost:8000/auth/callback" \
     --sign-in-audience "AzureADMyOrg"
   ```

2. Configure Environment Variables:
   ```bash
   # .env for development
   AZURE_TENANT_ID=your_tenant_id
   AZURE_CLIENT_ID=your_dev_client_id
   AZURE_CLIENT_SECRET=your_dev_client_secret
   AUTH_REDIRECT_URI=http://localhost:8000/auth/callback
   ```

3. Configure CORS:
   ```python
   # backend/src/main.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### Local Development
1. Start Services:
   ```bash
   docker-compose up --build
   ```

2. Access Development URLs:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000
   - API Docs: http://localhost:8000/docs

3. Test Authentication:
   ```bash
   # Get test token
   curl -X POST http://localhost:8000/auth/token \
     -H "Content-Type: application/json" \
     -d '{"username": "test@example.com", "password": "test"}'
   ```

## Production Setup

### Azure AD Configuration
1. Register Production App:
   ```bash
   # Using Azure CLI
   az ad app create --display-name "Transcribo-Prod" \
     --web-redirect-uris "https://transcribo.example.com/auth/callback" \
     --sign-in-audience "AzureADMyOrg"
   ```

2. Configure Environment Variables:
   ```bash
   # Production environment
   AZURE_TENANT_ID=your_tenant_id
   AZURE_CLIENT_ID=your_prod_client_id
   AZURE_CLIENT_SECRET=your_prod_client_secret
   AUTH_REDIRECT_URI=https://transcribo.example.com/auth/callback
   ```

3. Configure CORS:
   ```python
   # backend/src/main.py
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://transcribo.example.com"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )
   ```

### Security Configuration
1. Enable SSL:
   ```yaml
   # docker-compose.prod.yml
   services:
     traefik:
       command:
         - "--providers.docker=true"
         - "--entrypoints.websecure.address=:443"
         - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
   ```

2. Configure Rate Limiting:
   ```yaml
   # traefik.yml
   http:
     middlewares:
       rate-limit:
         rateLimit:
           average: 100
           burst: 50
   ```

3. Enable Security Headers:
   ```yaml
   # traefik.yml
   http:
     middlewares:
       security-headers:
         headers:
           stsSeconds: 31536000
           forceSTSHeader: true
   ```

## Token Management

### Development Tokens
1. Generate Test Token:
   ```python
   # scripts/generate_test_token.py
   from backend.src.utils.token_validation import create_token

   token = create_token(
       user_id="test-user",
       email="test@example.com",
       roles=["user"]
   )
   print(f"Test token: {token}")
   ```

2. Validate Test Token:
   ```python
   # scripts/validate_test_token.py
   from backend.src.utils.token_validation import validate_token

   is_valid = validate_token(token)
   print(f"Token valid: {is_valid}")
   ```

### Production Tokens
1. Token Configuration:
   ```python
   # backend/src/config.py
   TOKEN_EXPIRY = 3600  # 1 hour
   REFRESH_TOKEN_EXPIRY = 2592000  # 30 days
   ```

2. Token Rotation:
   ```python
   # backend/src/services/auth.py
   async def rotate_refresh_token(user_id: str) -> str:
       """Generate new refresh token and invalidate old one"""
       await invalidate_old_tokens(user_id)
       return create_refresh_token(user_id)
   ```

## Role-Based Access Control

### Development Roles
1. Available Roles:
   ```python
   # backend/src/models/user.py
   class UserRole(str, Enum):
       ADMIN = "admin"
       USER = "user"
       VIEWER = "viewer"
   ```

2. Role Assignment:
   ```python
   # backend/src/routes/auth.py
   @router.post("/assign-role")
   async def assign_role(
       user_id: str,
       role: UserRole,
       current_user: User = Depends(get_current_user)
   ):
       if current_user.role != UserRole.ADMIN:
           raise HTTPException(403, "Not authorized")
       await assign_user_role(user_id, role)
   ```

### Production Roles
1. Role Mapping:
   ```python
   # backend/src/services/auth.py
   AZURE_ROLE_MAPPING = {
       "Transcribo.Admin": UserRole.ADMIN,
       "Transcribo.User": UserRole.USER,
       "Transcribo.Viewer": UserRole.VIEWER
   }
   ```

2. Role Validation:
   ```python
   # backend/src/middleware/auth.py
   def require_role(role: UserRole):
       def decorator(func):
           @wraps(func)
           async def wrapper(*args, **kwargs):
               user = kwargs.get("current_user")
               if user.role != role:
                   raise HTTPException(403, "Not authorized")
               return await func(*args, **kwargs)
           return wrapper
       return decorator
   ```

## Error Handling

### Development Errors
1. Authentication Errors:
   ```python
   # backend/src/utils/exceptions.py
   class AuthenticationError(Exception):
       """Base class for authentication errors"""
       pass

   class TokenExpiredError(AuthenticationError):
       """Token has expired"""
       pass
   ```

2. Error Responses:
   ```python
   # backend/src/middleware/error_handler.py
   @app.exception_handler(AuthenticationError)
   async def auth_exception_handler(request, exc):
       return JSONResponse(
           status_code=401,
           content={"error": str(exc)}
       )
   ```

### Production Errors
1. Error Logging:
   ```python
   # backend/src/middleware/error_handler.py
   @app.exception_handler(AuthenticationError)
   async def auth_exception_handler(request, exc):
       logger.error(
           "Authentication error",
           extra={
               "error": str(exc),
               "user_id": request.state.user_id,
               "path": request.url.path
           }
       )
       return JSONResponse(
           status_code=401,
           content={"error": "Authentication failed"}
       )
   ```

2. Error Metrics:
   ```python
   # backend/src/middleware/metrics.py
   AUTH_ERRORS = Counter(
       "auth_errors_total",
       "Total authentication errors",
       ["error_type"]
   )
   ```

## Testing

### Development Testing
1. Test Users:
   ```python
   # tests/conftest.py
   @pytest.fixture
   def test_user():
       return User(
           id="test-user",
           email="test@example.com",
           role=UserRole.USER
       )
   ```

2. Test Tokens:
   ```python
   # tests/conftest.py
   @pytest.fixture
   def test_token():
       return create_token(
           user_id="test-user",
           email="test@example.com",
           roles=["user"]
       )
   ```

### Production Testing
1. Integration Tests:
   ```python
   # tests/integration/test_auth.py
   async def test_azure_auth_flow():
       # Test complete auth flow
       response = await client.post(
           "/auth/login",
           json={"code": "test-code"}
       )
       assert response.status_code == 200
       assert "access_token" in response.json()
   ```

2. Load Tests:
   ```python
   # tests/load/test_auth.py
   def test_auth_performance():
       # Test auth endpoints under load
       for _ in range(100):
           response = client.post(
               "/auth/token",
               json={"refresh_token": "test-token"}
           )
           assert response.status_code == 200
   ```

## Monitoring

### Development Monitoring
1. Log Configuration:
   ```python
   # backend/src/utils/logging.py
   logger.add(
       "logs/auth.log",
       level="DEBUG",
       rotation="1 day"
   )
   ```

2. Metrics Setup:
   ```python
   # backend/src/utils/metrics.py
   AUTH_REQUESTS = Counter(
       "auth_requests_total",
       "Total authentication requests",
       ["endpoint"]
   )
   ```

### Production Monitoring
1. Log Aggregation:
   ```yaml
   # docker-compose.prod.yml
   services:
     loki:
       image: grafana/loki
       volumes:
         - ./infrastructure/loki:/etc/loki
   ```

2. Alert Configuration:
   ```yaml
   # prometheus/alerts.yml
   groups:
     - name: auth
       rules:
         - alert: HighAuthFailureRate
           expr: rate(auth_errors_total[5m]) > 0.1
           for: 5m
   ```

## Maintenance

### Development Maintenance
1. Token Cleanup:
   ```python
   # scripts/cleanup_tokens.py
   async def cleanup_expired_tokens():
       """Remove expired refresh tokens"""
       await db.execute(
           "DELETE FROM refresh_tokens WHERE expires_at < NOW()"
       )
   ```

2. Role Cleanup:
   ```python
   # scripts/cleanup_roles.py
   async def cleanup_orphaned_roles():
       """Remove roles for deleted users"""
       await db.execute(
           "DELETE FROM user_roles WHERE user_id NOT IN (SELECT id FROM users)"
       )
   ```

### Production Maintenance
1. Certificate Rotation:
   ```bash
   # Rotate SSL certificates
   docker-compose exec traefik certbot renew
   ```

2. Secret Rotation:
   ```bash
   # Rotate client secrets
   az ad app credential reset --id $APP_ID
