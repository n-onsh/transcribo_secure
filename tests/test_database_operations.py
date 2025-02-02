# tests/test_database_operations.py
import pytest
from backend_api.src.services.database import DatabaseService

@pytest.fixture(scope="module")
def db_service():
    # Instantiate the DatabaseService with short retry settings for testing.
    service = DatabaseService(max_retries=1, retry_delay=1)
    yield service
    service.close()

@pytest.mark.asyncio
async def test_initialize_and_health_check(db_service):
    # Initialize the database schema.
    await db_service.initialize_database()
    # Perform a health check.
    healthy = await db_service.health_check()
    assert healthy is True
