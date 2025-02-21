import os
import logging
from typing import Optional, List, Dict
import asyncpg
from datetime import datetime, timedelta
import uuid
from ..models.user import User
from ..models.job import Job, JobStatus
from ..models.vocabulary import VocabularyList
from ..utils.metrics import (
    DB_OPERATION_DURATION,
    DB_OPERATION_ERRORS,
    DB_CONNECTIONS,
    track_time,
    track_errors,
    update_gauge
)

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        """Initialize database service"""
        # Get configuration
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.port = int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = os.getenv("POSTGRES_DB", "transcribo")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD")
        
        if not self.password:
            raise ValueError("POSTGRES_PASSWORD environment variable not set")
        
        # Initialize connection pool
        self.pool = None
        
        logger.info("Database service initialized")

    @track_time(DB_OPERATION_DURATION, {"operation": "initialize"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "initialize"})
    async def initialize_database(self):
        """Initialize database connection and tables"""
        try:
            # Create connection pool
            self.pool = await asyncpg.create_pool(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                min_size=5,
                max_size=20
            )
            
            # Create tables
            async with self.pool.acquire() as conn:
                await self._create_tables(conn)
            
            # Update connection metrics
            update_gauge(DB_CONNECTIONS, len(self.pool._holders))
            
            logger.info("Database initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}")
            raise

    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            update_gauge(DB_CONNECTIONS, 0)
            logger.info("Database connection closed")

    async def get_active_connections(self) -> int:
        """Get number of active connections"""
        return len(self.pool._holders) if self.pool else 0

    @track_time(DB_OPERATION_DURATION, {"operation": "create_tables"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "create_tables"})
    async def _create_tables(self, conn):
        """Create database tables"""
        try:
            # Users table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    hashed_password TEXT NOT NULL,
                    roles TEXT[] NOT NULL DEFAULT '{user}',
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_login TIMESTAMP,
                    settings JSONB NOT NULL DEFAULT '{}',
                    metadata JSONB NOT NULL DEFAULT '{}'
                )
            """)
            
            # Jobs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    file_name TEXT NOT NULL,
                    file_size BIGINT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    progress FLOAT NOT NULL DEFAULT 0.0,
                    error TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMP,
                    metadata JSONB NOT NULL DEFAULT '{}'
                )
            """)
            
            # Vocabulary table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    word TEXT NOT NULL,
                    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, word)
                )
            """)
            
            logger.info("Database tables created")
            
        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise

    # User operations
    @track_time(DB_OPERATION_DURATION, {"operation": "create_user"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "create_user"})
    async def create_user(self, user: User) -> User:
        """Create new user"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO users (
                    id, email, name, hashed_password, roles,
                    created_at, updated_at, settings, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
            """, user.id, user.email, user.name, user.hashed_password,
                user.roles, user.created_at, user.updated_at,
                user.settings, user.metadata)
            
            return User.parse_obj(dict(row))

    @track_time(DB_OPERATION_DURATION, {"operation": "get_user"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_user"})
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE id = $1",
                user_id
            )
            return User.parse_obj(dict(row)) if row else None

    @track_time(DB_OPERATION_DURATION, {"operation": "get_user_by_email"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_user_by_email"})
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE email = $1",
                email
            )
            return User.parse_obj(dict(row)) if row else None

    @track_time(DB_OPERATION_DURATION, {"operation": "update_user"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "update_user"})
    async def update_user(self, user: User) -> User:
        """Update user"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE users
                SET email = $2, name = $3, hashed_password = $4,
                    roles = $5, updated_at = $6, last_login = $7,
                    settings = $8, metadata = $9
                WHERE id = $1
                RETURNING *
            """, user.id, user.email, user.name, user.hashed_password,
                user.roles, user.updated_at, user.last_login,
                user.settings, user.metadata)
            
            return User.parse_obj(dict(row))

    @track_time(DB_OPERATION_DURATION, {"operation": "delete_user"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "delete_user"})
    async def delete_user(self, user_id: str):
        """Delete user"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM users WHERE id = $1",
                user_id
            )

    @track_time(DB_OPERATION_DURATION, {"operation": "list_users"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "list_users"})
    async def list_users(self) -> List[User]:
        """List all users"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
            return [User.parse_obj(dict(row)) for row in rows]

    # Job operations
    @track_time(DB_OPERATION_DURATION, {"operation": "create_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "create_job"})
    async def create_job(self, job: Job) -> Job:
        """Create new job"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO jobs (
                    id, user_id, file_name, file_size, status,
                    progress, created_at, updated_at, metadata
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
            """, job.id, job.user_id, job.file_name, job.file_size,
                job.status, job.progress, job.created_at,
                job.updated_at, job.metadata)
            
            return Job.parse_obj(dict(row))

    @track_time(DB_OPERATION_DURATION, {"operation": "get_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_job"})
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM jobs WHERE id = $1",
                job_id
            )
            return Job.parse_obj(dict(row)) if row else None

    @track_time(DB_OPERATION_DURATION, {"operation": "update_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "update_job"})
    async def update_job(self, job: Job) -> Job:
        """Update job"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                UPDATE jobs
                SET status = $2, progress = $3, error = $4,
                    updated_at = $5, completed_at = $6,
                    metadata = $7
                WHERE id = $1
                RETURNING *
            """, job.id, job.status, job.progress, job.error,
                job.updated_at, job.completed_at, job.metadata)
            
            return Job.parse_obj(dict(row))

    @track_time(DB_OPERATION_DURATION, {"operation": "delete_job"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "delete_job"})
    async def delete_job(self, job_id: str):
        """Delete job"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM jobs WHERE id = $1",
                job_id
            )

    @track_time(DB_OPERATION_DURATION, {"operation": "list_jobs"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "list_jobs"})
    async def list_jobs(
        self,
        user_id: Optional[str] = None,
        status: Optional[JobStatus] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[Job]:
        """List jobs with filtering"""
        async with self.pool.acquire() as conn:
            # Build query
            query = ["SELECT * FROM jobs"]
            params = []
            
            # Add filters
            filters = []
            if user_id:
                params.append(user_id)
                filters.append(f"user_id = ${len(params)}")
            if status:
                params.append(status)
                filters.append(f"status = ${len(params)}")
            
            if filters:
                query.append("WHERE " + " AND ".join(filters))
            
            # Add pagination
            query.append("ORDER BY created_at DESC")
            if limit:
                params.append(limit)
                query.append(f"LIMIT ${len(params)}")
            if offset:
                params.append(offset)
                query.append(f"OFFSET ${len(params)}")
            
            # Execute query
            rows = await conn.fetch(" ".join(query), *params)
            return [Job.parse_obj(dict(row)) for row in rows]

    @track_time(DB_OPERATION_DURATION, {"operation": "cleanup_jobs"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "cleanup_jobs"})
    async def cleanup_old_jobs(self, days: int):
        """Delete old completed jobs"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM jobs
                WHERE status = 'completed'
                AND completed_at < $1
            """, cutoff)

    # Vocabulary operations
    @track_time(DB_OPERATION_DURATION, {"operation": "add_vocabulary"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "add_vocabulary"})
    async def add_vocabulary_word(
        self,
        user_id: str,
        word: str
    ) -> VocabularyList:
        """Add word to vocabulary"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO vocabulary (id, user_id, word)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id, word) DO NOTHING
            """, str(uuid.uuid4()), user_id, word)
            
            return await self.get_vocabulary(user_id)

    @track_time(DB_OPERATION_DURATION, {"operation": "remove_vocabulary"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "remove_vocabulary"})
    async def remove_vocabulary_word(
        self,
        user_id: str,
        word: str
    ) -> VocabularyList:
        """Remove word from vocabulary"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM vocabulary
                WHERE user_id = $1 AND word = $2
            """, user_id, word)
            
            return await self.get_vocabulary(user_id)

    @track_time(DB_OPERATION_DURATION, {"operation": "get_vocabulary"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "get_vocabulary"})
    async def get_vocabulary(self, user_id: str) -> VocabularyList:
        """Get user's vocabulary list"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT word, added_at
                FROM vocabulary
                WHERE user_id = $1
                ORDER BY added_at DESC
            """, user_id)
            
            return VocabularyList(
                user_id=user_id,
                words=[{
                    "word": row["word"],
                    "added_at": row["added_at"]
                } for row in rows]
            )

    @track_time(DB_OPERATION_DURATION, {"operation": "clear_vocabulary"})
    @track_errors(DB_OPERATION_ERRORS, {"operation": "clear_vocabulary"})
    async def clear_vocabulary(self, user_id: str):
        """Clear user's vocabulary"""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                DELETE FROM vocabulary
                WHERE user_id = $1
            """, user_id)
