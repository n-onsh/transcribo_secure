"""User repository."""

from typing import Optional, List, Dict, Any, cast
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import joinedload
from .base import BaseRepository
from .user import User, Role, Scope

class UserRepository(BaseRepository[User]):
    """Repository for user operations."""
    
    def __init__(self, session):
        """Initialize repository.
        
        Args:
            session: Database session
        """
        super().__init__(session, User)

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username.
        
        Args:
            username: Username to look up
            
        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                joinedload(User.roles),
                joinedload(User.scopes)
            )
            .where(User.username == username)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email.
        
        Args:
            email: Email to look up
            
        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                joinedload(User.roles),
                joinedload(User.scopes)
            )
            .where(User.email == email)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_with_roles_and_scopes(self, user_id: UUID) -> Optional[User]:
        """Get user with roles and scopes.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                joinedload(User.roles),
                joinedload(User.scopes)
            )
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def find_by_identity(self, identity: str) -> Optional[User]:
        """Find user by username or email.
        
        Args:
            identity: Username or email to look up
            
        Returns:
            User if found, None otherwise
        """
        stmt = (
            select(User)
            .options(
                joinedload(User.roles),
                joinedload(User.scopes)
            )
            .where(
                or_(
                    User.username == identity,
                    User.email == identity
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def update_last_login(self, user_id: UUID) -> None:
        """Update user's last login timestamp.
        
        Args:
            user_id: User ID to update
        """
        user = await self.get(user_id)
        if user:
            user.last_login = datetime.utcnow()
            await self.session.commit()

    async def add_role(self, user_id: UUID, role_name: str) -> bool:
        """Add role to user.
        
        Args:
            user_id: User ID to update
            role_name: Role name to add
            
        Returns:
            True if role was added, False if user or role not found
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return False
            
        # Get role
        stmt = select(Role).where(Role.name == role_name)
        result = await self.session.execute(stmt)
        role = result.scalar_one_or_none()
        
        if not role:
            return False
            
        # Add role if not already present
        if role not in user.roles:
            user.roles.append(role)
            await self.session.commit()
            
        return True

    async def remove_role(self, user_id: UUID, role_name: str) -> bool:
        """Remove role from user.
        
        Args:
            user_id: User ID to update
            role_name: Role name to remove
            
        Returns:
            True if role was removed, False if user or role not found
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return False
            
        # Get role
        stmt = select(Role).where(Role.name == role_name)
        result = await self.session.execute(stmt)
        role = result.scalar_one_or_none()
        
        if not role:
            return False
            
        # Remove role if present
        if role in user.roles:
            user.roles.remove(role)
            await self.session.commit()
            
        return True

    async def add_scope(self, user_id: UUID, scope_name: str) -> bool:
        """Add scope to user.
        
        Args:
            user_id: User ID to update
            scope_name: Scope name to add
            
        Returns:
            True if scope was added, False if user or scope not found
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return False
            
        # Get scope
        stmt = select(Scope).where(Scope.name == scope_name)
        result = await self.session.execute(stmt)
        scope = result.scalar_one_or_none()
        
        if not scope:
            return False
            
        # Add scope if not already present
        if scope not in user.scopes:
            user.scopes.append(scope)
            await self.session.commit()
            
        return True

    async def remove_scope(self, user_id: UUID, scope_name: str) -> bool:
        """Remove scope from user.
        
        Args:
            user_id: User ID to update
            scope_name: Scope name to remove
            
        Returns:
            True if scope was removed, False if user or scope not found
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return False
            
        # Get scope
        stmt = select(Scope).where(Scope.name == scope_name)
        result = await self.session.execute(stmt)
        scope = result.scalar_one_or_none()
        
        if not scope:
            return False
            
        # Remove scope if present
        if scope in user.scopes:
            user.scopes.remove(scope)
            await self.session.commit()
            
        return True

    async def get_roles(self, user_id: UUID) -> List[str]:
        """Get user's roles.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            List of role names
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return []
            
        return [role.name for role in user.roles]

    async def get_scopes(self, user_id: UUID) -> List[str]:
        """Get user's scopes.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            List of scope names
        """
        user = await self.get_with_roles_and_scopes(user_id)
        if not user:
            return []
            
        return [scope.name for scope in user.scopes]

    async def create_user(
        self,
        username: str,
        email: Optional[str] = None,
        password_hash: Optional[str] = None,
        roles: Optional[List[str]] = None,
        scopes: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[User]:
        """Create a new user.
        
        Args:
            username: Username
            email: Optional email
            password_hash: Optional password hash
            roles: Optional list of role names
            scopes: Optional list of scope names
            metadata: Optional metadata
            
        Returns:
            Created user if successful, None if username/email exists
        """
        # Check if username/email exists
        existing = await self.find_by_identity(username)
        if existing:
            return None
            
        if email:
            existing = await self.find_by_identity(email)
            if existing:
                return None
        
        # Create user
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            metadata=metadata or {}
        )
        
        # Add roles
        if roles:
            stmt = select(Role).where(Role.name.in_(roles))
            result = await self.session.execute(stmt)
            user.roles.extend(result.scalars().all())
            
        # Add scopes
        if scopes:
            stmt = select(Scope).where(Scope.name.in_(scopes))
            result = await self.session.execute(stmt)
            user.scopes.extend(result.scalars().all())
            
        self.session.add(user)
        await self.session.commit()
        
        return user
