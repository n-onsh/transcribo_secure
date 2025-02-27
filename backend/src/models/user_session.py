"""User session model."""

from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .user import User

class UserSession(Base):
    """User session model for storing authentication sessions."""
    
    __tablename__ = 'user_sessions'
    
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    refresh_token_hash: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    user_agent: Mapped[Optional[str]] = mapped_column(String)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))  # IPv6 addresses can be up to 45 chars
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    
    # Relationships
    user: Mapped[User] = relationship('User', back_populates='sessions')
