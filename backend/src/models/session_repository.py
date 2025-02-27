"""Session repository."""

from typing import Optional, List
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, update, and_, or_
from sqlalchemy.orm import joinedload
from .base import BaseRepository
from .user_session import UserSession

class SessionRepository(BaseRepository[UserSession]):
    """Repository for user session operations."""
    
    def __init__(self, session):
        """Initialize repository.
        
        Args:
            session: Database session
        """
        super().__init__(session, UserSession)

    async def get_by_token_hash(self, token_hash: str) -> Optional[UserSession]:
        """Get session by token hash.
        
        Args:
            token_hash: Token hash to look up
            
        Returns:
            Session if found, None otherwise
        """
        stmt = (
            select(UserSession)
            .options(joinedload(UserSession.user))
            .where(UserSession.token_hash == token_hash)
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_active_sessions(self, user_id: UUID) -> List[UserSession]:
        """Get all active sessions for user.
        
        Args:
            user_id: User ID to look up
            
        Returns:
            List of active sessions
        """
        stmt = (
            select(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True,
                    UserSession.expires_at > datetime.utcnow()
                )
            )
            .order_by(UserSession.last_used_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_session(
        self,
        user_id: UUID,
        token_hash: str,
        refresh_token_hash: Optional[str] = None,
        expires_at: datetime = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> UserSession:
        """Create a new user session.
        
        Args:
            user_id: User ID
            token_hash: Hashed access token
            refresh_token_hash: Optional hashed refresh token
            expires_at: Optional expiration time
            user_agent: Optional user agent string
            ip_address: Optional IP address
            
        Returns:
            Created session
        """
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at or datetime.utcnow(),
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        self.session.add(session)
        await self.session.commit()
        return session

    async def update_last_used(self, session_id: UUID) -> bool:
        """Update session's last used timestamp.
        
        Args:
            session_id: Session ID to update
            
        Returns:
            True if session was updated, False if not found
        """
        session = await self.get(session_id)
        if not session:
            return False
            
        session.last_used_at = datetime.utcnow()
        await self.session.commit()
        return True

    async def invalidate_session(self, session_id: UUID) -> bool:
        """Invalidate a session.
        
        Args:
            session_id: Session ID to invalidate
            
        Returns:
            True if session was invalidated, False if not found
        """
        session = await self.get(session_id)
        if not session:
            return False
            
        session.is_active = False
        await self.session.commit()
        return True

    async def invalidate_all_user_sessions(self, user_id: UUID) -> int:
        """Invalidate all sessions for a user.
        
        Args:
            user_id: User ID to invalidate sessions for
            
        Returns:
            Number of sessions invalidated
        """
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.user_id == user_id,
                    UserSession.is_active == True
                )
            )
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions.
        
        Returns:
            Number of sessions cleaned up
        """
        stmt = (
            update(UserSession)
            .where(
                and_(
                    UserSession.is_active == True,
                    UserSession.expires_at <= datetime.utcnow()
                )
            )
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
