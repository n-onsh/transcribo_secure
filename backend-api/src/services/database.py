import os
import psycopg2
from psycopg2.extras import RealDictCursor
from ..models.file import FileMetadata
from pydantic import UUID4
from typing import Optional
from ..models.job import Job, JobStatus, JobUpdate

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
        
async def init_jobs_table(self):
    """Initialize jobs table"""
    with self.conn.cursor() as cur:
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
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
            CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_file_id ON jobs(file_id);
        """)
        self.conn.commit()

async def create_job(self, job: Job) -> Job:
    """Create a new job"""
    with self.conn.cursor() as cur:
        cur.execute("""
            INSERT INTO jobs (
                job_id, file_id, user_id, job_type, status,
                created_at, updated_at, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (
            job.job_id, job.file_id, job.user_id, job.job_type,
            job.status, job.created_at, job.updated_at, job.metadata
        ))
        self.conn.commit()
        result = cur.fetchone()
        return Job(**dict(zip([col[0] for col in cur.description], result)))

async def update_job(self, job_id: UUID4, update: JobUpdate) -> Optional[Job]:
    """Update job status and progress"""
    update_fields = []
    update_values = []
    
    # Build dynamic update query based on provided fields
    if update.status:
        update_fields.append("status = %s")
        update_values.append(update.status)
    if update.progress is not None:
        update_fields.append("progress = %s")
        update_values.append(update.progress)
    if update.error_message is not None:
        update_fields.append("error_message = %s")
        update_values.append(update.error_message)
    if update.metadata is not None:
        update_fields.append("metadata = %s")
        update_values.append(update.metadata)
    
    update_fields.append("updated_at = CURRENT_TIMESTAMP")
    
    if update.status == JobStatus.PROCESSING and "started_at IS NULL" not in update_fields:
        update_fields.append("started_at = CURRENT_TIMESTAMP")
    elif update.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
        update_fields.append("completed_at = CURRENT_TIMESTAMP")

    with self.conn.cursor() as cur:
        cur.execute(f"""
            UPDATE jobs
            SET {", ".join(update_fields)}
            WHERE job_id = %s
            RETURNING *
        """, [*update_values, job_id])
        self.conn.commit()
        result = cur.fetchone()
        if result:
            return Job(**dict(zip([col[0] for col in cur.description], result)))
        return None

async def get_job(self, job_id: UUID4) -> Optional[Job]:
    """Get job by ID"""
    with self.conn.cursor() as cur:
        cur.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
        result = cur.fetchone()
        if result:
            return Job(**dict(zip([col[0] for col in cur.description], result)))
        return None

async def get_pending_jobs(self, limit: int = 10) -> list[Job]:
    """Get pending jobs for processing"""
    with self.conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM jobs 
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT %s
        """, (limit,))
        results = cur.fetchall()
        return [
            Job(**dict(zip([col[0] for col in cur.description], row)))
            for row in results
        ]

async def get_jobs_by_user(
    self,
    user_id: str,
    status: Optional[JobStatus] = None,
    limit: int = 100,
    offset: int = 0
) -> list[Job]:
    """Get jobs for a specific user"""
    query = "SELECT * FROM jobs WHERE user_id = %s"
    params = [user_id]
    
    if status:
        query += " AND status = %s"
        params.append(status)
    
    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    
    with self.conn.cursor() as cur:
        cur.execute(query, params)
        results = cur.fetchall()
        return [
            Job(**dict(zip([col[0] for col in cur.description], row)))
            for row in results
        ]
    
async def get_job_stats(self) -> dict:
    """Get job statistics for each status"""
    with self.conn.cursor() as cur:
        cur.execute("""
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
        """)
        results = cur.fetchall()
        return {
            status: count
            for status, count in results
        }