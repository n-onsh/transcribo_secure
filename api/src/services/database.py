import os
import psycopg2
from psycopg2.extras import RealDictCursor

class DatabaseService:
    def __init__(self):
        self.conn = psycopg2.connect(
            dbname=os.getenv("POSTGRES_DB"),
            user=os.getenv("POSTGRES_USER"),
            password=os.getenv("POSTGRES_PASSWORD"),
            host=os.getenv("POSTGRES_HOST"),
            port=os.getenv("POSTGRES_PORT", "5432")
        )

    async def init_db(self):
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
            """)
            self.conn.commit()