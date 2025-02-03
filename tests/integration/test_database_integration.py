# tests/integration/test_database_integration.py
import os
import asyncio
import pytest
from testcontainers.postgres import PostgresContainer
from backend_api.src.services.database import DatabaseService

@pytest.fixture(scope="module")
def postgres_container():
    # Start a Postgres container
    with PostgresContainer("postgres:15") as postgres:
        # Override the environment variables so that our DatabaseService connects to this container.
        os.environ["POSTGRES_DB"] = postgres.DB_NAME
        os.environ["POSTGRES_USER"] = postgres.USER
        os.environ["POSTGRES_PASSWORD"] = postgres.PASSWORD
        os.environ["POSTGRES_HOST"] = postgres.get_container_host_ip()
        os.environ["POSTGRES_PORT"] = postgres.get_exposed_port(postgres.port)
        yield postgres

@pytest.mark.asyncio
async def test_postgres_health(postgres_container):
    db_service = DatabaseService(max_retries=3, retry_delay=1)
    # Initialize the database (schema creation)
    await db_service.initialize_database()
    healthy = await db_service.health_check()
    assert healthy is True
    await db_service.close()
