"""User service."""

from typing import Optional, List, Dict, Any, cast
from uuid import UUID
from datetime import datetime, timedelta
from jose import jwt, JWTError
from ..models.user import User
from ..models.user_repository import UserRepository
from ..types import (
    JWTPayload,
    JWTToken,
    UserInfo,
    ErrorContext
)
from ..utils.exceptions import (
    AuthenticationError,
    ValidationError,
    ConfigurationError
)
from ..utils.logging import log_info, log_error, log_warning
from ..utils.metrics import (
    AUTH_OPERATIONS,
    AUTH_ERRORS,
    track_auth_operation,
    track_auth_error
)
from .base import BaseService
from ..config import config

class UserService(BaseService):
    """Service for user operations."""

    def __init__(self, settings: Dict[str, Any]):
        """Initialize service.
        
        Args:
            settings: Service settings
        """
        super().__init__(settings)
        self.user_repository: Optional[UserRepository] = None

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize user repository
            self.user_repository = UserRepository(self.db_session)
            log_info("User service initialized")

        except Exception as e:
            error_context: ErrorContext = {
                "operation": "initialize_user_service",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Failed to initialize user service: {str(e)}")
            raise ConfigurationError(
                "Failed to initialize user service",
                details=error_context
            )

    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User if found, None otherwise
        """
        self._check_initialized()
        return await self.user_repository.get_with_roles_and_scopes(user_id)

    async def get_user_by_identity(self, identity: str) -> Optional[User]:
        """Get user by username or email.
        
        Args:
            identity: Username or email to look up
            
        Returns:
            User if found, None otherwise
        """
        self._check_initialized()
        return await self.user_repository.find_by_identity(identity)

    async def create_user(
        self,
        username: str,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        roles: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> User:
        """Create a new user.
        
        Args:
            username: Username
            email: Optional email
            password_hash: Optional password hash
            roles: Optional list of role names
            scopes: Optional list of scope names
            metadata: Optional metadata
            
        Returns:
            Created user
            
        Raises:
            ValidationError: If username/email exists
        """
        self._check_initialized()
        
        # Track operation
        AUTH_OPERATIONS.labels(operation='create_user').inc()
        track_auth_operation('create_user')
        
        try:
            user = await self.user_repository.create_user(
                username=username,
                email=email,
                password_hash=password_hash,
                roles=roles or ['user'],  # Default to user role
                scopes=scopes,
                metadata=metadata
            )
            
            if not user:
                error_context: ErrorContext = {
                    "operation": "create_user",
                    "timestamp": datetime.utcnow(),
                    "details": {
                        "username": username,
                        "email": email
                    }
                }
                raise ValidationError(
                    "Username or email already exists",
                    details=error_context
                )
                
            log_info(f"Created user {username}")
            return user
            
        except ValidationError:
            AUTH_ERRORS.inc()
            track_auth_error()
            raise
        except Exception as e:
            AUTH_ERRORS.inc()
            track_auth_error()
            error_context = {
                "operation": "create_user",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "username": username,
                    "email": email
                }
            }
            log_error(f"Error creating user: {str(e)}")
            raise AuthenticationError(
                "Failed to create user",
                details=error_context
            )

    async def create_access_token(self, user: User) -> JWTToken:
        """Create access token for user.
        
        Args:
            user: User to create token for
            
        Returns:
            JWT token response
            
        Raises:
            AuthenticationError: If token creation fails
        """
        self._check_initialized()
        
        try:
            # Create access token
            access_token_expires = timedelta(
                minutes=config.auth.jwt_access_token_expire_minutes
            )
            access_token = self._create_token(
                user=user,
                expires_delta=access_token_expires
            )
            
            # Update last login
            await self.user_repository.update_last_login(user.id)
            
            return {
                'access_token': access_token,
                'token_type': 'bearer',
                'expires_in': config.auth.jwt_access_token_expire_minutes * 60
            }
            
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "create_access_token",
                "timestamp": datetime.utcnow(),
                "details": {
                    "error": str(e),
                    "user_id": str(user.id)
                }
            }
            log_error(f"Error creating access token: {str(e)}")
            raise AuthenticationError(
                "Failed to create access token",
                details=error_context
            )

    def _create_token(
        self,
        user: User,
        expires_delta: timedelta
    ) -> str:
        """Create JWT token.
        
        Args:
            user: User to create token for
            expires_delta: Token expiration time
            
        Returns:
            JWT token string
        """
        now = datetime.utcnow()
        expires = now + expires_delta
        
        to_encode: JWTPayload = {
            'sub': str(user.id),
            'exp': expires,
            'iat': now,
            'nbf': now,
            'roles': [role.name for role in user.roles],
            'scope': [scope.name for scope in user.scopes],
            'preferred_username': user.username,
            'email': user.email,
            'name': user.metadata.get('name')
        }
        
        return jwt.encode(
            to_encode,
            config.auth.jwt_secret_key,
            algorithm=config.auth.jwt_algorithm
        )

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate JWT token and return user.
        
        Args:
            token: JWT token string
            
        Returns:
            User if token is valid, None otherwise
            
        Raises:
            AuthenticationError: If token validation fails
        """
        self._check_initialized()
        
        try:
            # Decode and validate token
            payload = jwt.decode(
                token,
                config.auth.jwt_secret_key,
                algorithms=[config.auth.jwt_algorithm],
                options={
                    "verify_signature": True,
                    "verify_iat": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_sub": True,
                    "require_exp": True,
                    "require_iat": True,
                    "require_nbf": False
                }
            )
            
            # Get user
            user_id = UUID(payload['sub'])
            user = await self.get_user(user_id)
            
            if not user or not user.is_active:
                return None
                
            return user
            
        except JWTError as e:
            log_warning(f"JWT validation error: {str(e)}")
            return None
        except Exception as e:
            error_context: ErrorContext = {
                "operation": "validate_token",
                "timestamp": datetime.utcnow(),
                "details": {"error": str(e)}
            }
            log_error(f"Error validating token: {str(e)}")
            raise AuthenticationError(
                "Failed to validate token",
                details=error_context
            )
