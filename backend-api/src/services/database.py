import os
import psycopg2
from psycopg2.extras import RealDictCursor
from ..models.file import FileMetadata

class DatabaseService:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )

    async def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()

    async def init_db(self):
        """Initialize database tables"""
        with self.conn.cursor() as cur:
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
                );
                CREATE INDEX IF NOT EXISTS idx_files_user_id ON files(user_id);
                CREATE INDEX IF NOT EXISTS idx_files_created_at ON files(created_at);
            """)
            self.conn.commit()

    async def create_file(self, file: FileMetadata) -> FileMetadata:
        """Create a new file metadata record"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO files (
                    file_id, user_id, file_name, file_type,
                    created_at, size_bytes, content_type
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                file.file_id, file.user_id, file.file_name,
                file.file_type, file.created_at, file.size_bytes,
                file.content_type
            ))
            self.conn.commit()
            result = cur.fetchone()
            return FileMetadata(**dict(zip([col[0] for col in cur.description], result)))

    async def get_file(self, file_id: str) -> FileMetadata:
        """Retrieve file metadata by ID"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM files WHERE file_id = %s
            """, (file_id,))
            result = cur.fetchone()
            if result:
                return FileMetadata(**dict(zip([col[0] for col in cur.description], result)))
            return None

    async def list_user_files(self, user_id: str, limit: int = 100, offset: int = 0):
        """List files for a given user"""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM files 
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (user_id, limit, offset))
            results = cur.fetchall()
            return [
                FileMetadata(**dict(zip([col[0] for col in cur.description], row)))
                for row in results
            ]