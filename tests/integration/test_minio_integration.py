# tests/integration/test_minio_integration.py
import os
import io
import pytest
from testcontainers.core.container import DockerContainer
from backend_api.src.services.storage import StorageService
import asyncio

@pytest.fixture(scope="module")
def minio_container():
    # Start a MinIO container using the generic DockerContainer interface.
    container = DockerContainer("minio/minio:latest") \
        .with_exposed_ports(9000, 9001) \
        .with_env("MINIO_ROOT_USER", "minio_test") \
        .with_env("MINIO_ROOT_PASSWORD", "minio_test_password") \
        .with_command("server --console-address ':9001' /data")
    with container as c:
        host = c.get_container_host_ip()
        port = c.get_exposed_port(9000)
        os.environ["MINIO_HOST"] = host
        os.environ["MINIO_PORT"] = port
        os.environ["MINIO_ROOT_USER"] = "minio_test"
        os.environ["MINIO_ROOT_PASSWORD"] = "minio_test_password"
        yield c

@pytest.mark.asyncio
async def test_minio_store_and_retrieve(minio_container):
    storage = StorageService()
    file_id = "123e4567-e89b-12d3-a456-426614174000"
    file_name = "dummy.txt"
    file_type = "input"
    file_content = io.BytesIO(b"Hello, integration!")
    total_size = await storage.store_file(file_id=file_id,
                                          file_data=file_content,
                                          file_name=file_name,
                                          file_type=file_type,
                                          metadata={"dummy": "data"})
    assert total_size == len(b"Hello, integration!")
    retrieved = await storage.retrieve_file(file_id=file_id,
                                            file_name=file_name,
                                            file_type=file_type)
    # Depending on the encryption, adjust the assertion.
    content = retrieved.read()
    assert b"Hello, integration!" in content
