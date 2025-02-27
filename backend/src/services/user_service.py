"""User service."""

from typing import Optional, List, Dict, Any, cast
from uuid import UUID
from datetime import datetime, timedelta
import secrets
import hashlib
from jose import jwt, JWTError
from ..models.user import User
from ..models.user_repository import UserRepository
from ..models.session_repository import SessionRepository
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
        self.session_repository: Optional[SessionRepository] = None

    async def _initialize_impl(self) -> None:
        """Initialize service implementation."""
        try:
            # Initialize repositories
            self.user_repository = UserRepository(self.db_session)
            self.session_repository = SessionRepository(self.db_session)
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

    async def create_access_token(
        self,
        user: User,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> JWTToken:
        """Create access token for user.
        
        Args:
            user: User to create token for
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            JWT token response
            
        Raises:
            AuthenticationError: If token creation fails
        """
        self._check_initialized()
        
        try:
            # Generate tokens
            access_token = secrets.token_urlsafe(32)
            refresh_token = secrets.token_urlsafe(32)
            
            # Hash tokens for storage
            access_token_hash = hashlib.sha256(access_token.encode()).hexdigest()
            refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            
            # Set expiration
            expires_delta = timedelta(minutes=config.auth.jwt_access_token_expire_minutes)
            expires_at = datetime.utcnow() + expires_delta
            
            # Create session in database
            await self.session_repository.create_session(
                user_id=user.id,
                token_hash=access_token_hash,
                refresh_token_hash=refresh_token_hash,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
            # Update last login
            await self.user_repository.update_last_login(user.id)
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': 'bearer',
                'expires_in': int(expires_delta.total_seconds())
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

    async def validate_token(self, token: str) -> Optional[User]:
        """Validate token and return user.
        
        Args:
            token: Access token string
            
        Returns:
            User if token is valid, None otherwise
            
        Raises:
            AuthenticationError: If token validation fails
        """
        self._check_initialized()
        
        try:
            # Hash token for lookup
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Get session
            session = await self.session_repository.get_by_token_hash(token_hash)
            if not session or not session.is_active:
                return None
                
            # Check expiration
            if session.expires_at < datetime.utcnow():
                # Invalidate expired session
                await self.session_repository.invalidate_session(session.id)
                return None
                
            # Update last used timestamp
            await self.session_repository.update_last_used(session.id)
            
            # Get and validate user
            user = await self.get_user(session.user_id)
            if not user or not user.is_active:
                return None
                
            return user
            
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

    async def refresh_token(
        self,
        refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[JWTToken]:
        """Refresh access token using refresh token.
        
        Args:
            refresh_token: Refresh token string
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            New token response if successful, None otherwise
        """
        self._check_initialized()
        
        try:
            # Hash refresh token for lookup
            refresh_token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
            
            # Find session by refresh token
            session = await self.session_repository.get_by_token_hash(refresh_token_hash)
            if not session or not session.is_active:
                return None
                
            # Check expiration
            if session.expires_at < datetime.utcnow():
                await self.session_repository.invalidate_session(session.id)
                return None
                
            # Get user
            user = await self.get_user(session.user_id)
            if not user or not user.is_active:
                return None
                
            # Invalidate old session
            await self.session_repository.invalidate_session(session.id)
            
            # Create new session and tokens
            return await self.create_access_token(
                user=user,
                user_agent=user_agent,
                ip_address=ip_address
            )
            
        except Exception as e:
            log_error(f"Error refreshing token: {str(e)}")
            return None

    async def invalidate_session(self, token: str) -> bool:
        """Invalidate a session.
        
        Args:
            token: Access token to invalidate
            
        Returns:
            True if session was invalidated, False otherwise
        """
        self._check_initialized()
        
        try:
            # Hash token for lookup
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Get session
            session = await self.session_repository.get_by_token_hash(token_hash)
            if not session:
                return False
                
            # Invalidate session
            return await self.session_repository.invalidate_session(session.id)
            
        except Exception as e:
            log_error(f"Error invalidating session: {str(e)}")
            return False

    async def invalidate_all_user_sessions(self, user_id: UUID) -> int:
        """Invalidate all sessions for a user.
        
        Args:
            user_id: User ID to invalidate sessions for
            
        Returns:
            Number of sessions invalidated
        """
        self._check_initialized()
        return await self.session_repository.invalidate_all_user_sessions(user_id)

    async def get_active_sessions(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get all active sessions for user.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            List of active session info dictionaries
        """
        self._check_initialized()
        
        sessions = await self.session_repository.get_active_sessions(user_id)
        return [
            {
                'id': str(session.id),
                'created_at': session.created_at.isoformat(),
                'last_used_at': session.last_used_at.isoformat(),
                'expires_at': session.expires_at.isoformat(),
                'user_agent': session.user_agent,
                'ip_address': session.ip_address
            }
            for session in sessions
        ]

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        self._check_initialized()
        return await self.session_repository.cleanup_expired_sessions()
