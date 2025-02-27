"""User model."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Table, Column
from sqlalchemy.dialects.postgresql import UUID as PGUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

# Association tables
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('role_id', PGUUID(as_uuid=True), ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
)

user_scopes = Table(
    'user_scopes',
    Base.metadata,
    Column('user_id', PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    Column('scope_id', PGUUID(as_uuid=True), ForeignKey('scopes.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
)

class Role(Base):
    """Role model."""
    
    __tablename__ = 'roles'
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    
    # Relationships
    users = relationship('User', secondary=user_roles, back_populates='roles')

class Scope(Base):
    """Scope model."""
    
    __tablename__ = 'scopes'
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    
    # Relationships
    users = relationship('User', secondary=user_scopes, back_populates='scopes')

class User(Base):
    """User model."""
    
    __tablename__ = 'users'
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    
    # Relationships
    roles: Mapped[List[Role]] = relationship(secondary=user_roles, back_populates='users')
    scopes: Mapped[List[Scope]] = relationship(secondary=user_scopes, back_populates='users')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary.
        
        Returns:
            Dictionary representation of user
        """
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'metadata': self.metadata,
            'roles': [role.name for role in self.roles],
            'scopes': [scope.name for scope in self.scopes]
        }
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role.
        
        Returns:
            True if user has admin role, False otherwise
        """
        return any(role.name == 'admin' for role in self.roles)
    
    def has_role(self, role_name: str) -> bool:
        """Check if user has specific role.
        
        Args:
            role_name: Role name to check
            
        Returns:
            True if user has role, False otherwise
        """
        return any(role.name == role_name for role in self.roles)
    
    def has_scope(self, scope_name: str) -> bool:
        """Check if user has specific scope.
        
        Args:
            scope_name: Scope name to check
            
        Returns:
            True if user has scope, False otherwise
        """
        return any(scope.name == scope_name for scope in self.scopes)
    
    def has_permission(self, resource: str, action: str) -> bool:
        """Check if user has permission for resource action.
        
        Args:
            resource: Resource name (e.g., 'files', 'jobs')
            action: Action name (e.g., 'read', 'write')
            
        Returns:
            True if user has permission, False otherwise
        """
        if self.is_admin:
            return True
            
        scope = f"{resource}:{action}"
        return self.has_scope(scope)
