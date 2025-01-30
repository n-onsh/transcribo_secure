import os
import time
import psycopg2
import psycopg2.extras
import logging
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseService:
    """Database service for managing PostgreSQL connections and operations"""
    
    def __init__(self, max_retries: int = 5, retry_delay: int = 5):
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._connect_with_retries()

    def _connect_with_retries(self):
        """Establish database connection with retry logic"""
        for attempt in range(self.max_retries):
            try:
                self.conn = psycopg2.connect(
                    dbname=os.getenv("POSTGRES_DB"),
                    user=os.getenv("POSTGRES_USER"),
                    password=os.getenv("POSTGRES_PASSWORD"),
                    host=os.getenv("POSTGRES_HOST"),
                    port=os.getenv("POSTGRES_PORT", "5432")
                )
                self.conn.autocommit = False  # Explicit transaction management
                logger.info("Successfully connected to database")
                return
            except psycopg2.OperationalError as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to connect to database after {self.max_retries} attempts")
                    raise
                logger.warning(f"Database connection attempt {attempt + 1} failed. Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff

    async def initialize_database(self):
        """Initialize database schema"""
        try:
            with self.conn.cursor() as cur:
                # Create files table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS files (
                        file_id UUID PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        file_name VARCHAR(255) NOT NULL,
                        file_type VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        size_bytes BIGINT NOT NULL,
                        content_type VARCHAR(100),
                        metadata JSONB
                    )
                """)

                # Create jobs table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id UUID PRIMARY KEY,
                        file_id UUID NOT NULL REFERENCES files(file_id),
                        user_id VARCHAR(255) NOT NULL,
                        job_type VARCHAR(50) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        started_at TIMESTAMP,
                        completed_at TIMESTAMP,
                        error_message TEXT,
                        progress FLOAT DEFAULT 0.0,
                        metadata JSONB,
                        CONSTRAINT valid_progress CHECK (progress >= 0 AND progress <= 100)
                    )
                """)

                # Create vocabulary table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vocabulary (
                        id UUID PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        word TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
                    CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at);
                    CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
                    CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
                    CREATE INDEX IF NOT EXISTS idx_vocabulary_user_id ON vocabulary(user_id);
                """)

                self.conn.commit()
                logger.info("Database initialization completed successfully")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error initializing database: {str(e)}")
            raise

    async def health_check(self) -> bool:
        """Check if database connection is healthy"""
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                return cur.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False

    async def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")

    def __del__(self):
        """Ensure connection is closed on object destruction"""
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()