"""
Integration tests for logging flow.

Critical aspects:
1. Log collection by OpenTelemetry collector
2. Log storage in Loki
3. Log correlation with traces
4. Log attribute indexing
"""
import pytest
import aiohttp
import json
import asyncio
from datetime import datetime, timedelta
from backend.src.services.keyvault import KeyVaultService
from backend.src.services.cleanup import CleanupService
from backend.src.services.storage import StorageService

class TestLoggingFlow:
    """Test suite for end-to-end logging flow."""

    @pytest.fixture
    async def loki_client(self):
        """Create a client for querying Loki."""
        async with aiohttp.ClientSession() as session:
            yield session

    async def query_loki(self, client, query: str, start_time: datetime, end_time: datetime):
        """Query Loki for logs."""
        params = {
            'query': query,
            'start': str(int(start_time.timestamp() * 1e9)),
            'end': str(int(end_time.timestamp() * 1e9)),
            'limit': 1000
        }
        async with client.get('http://localhost:3100/loki/api/v1/query_range', params=params) as response:
            return await response.json()

    async def test_log_collection(self, loki_client):
        """Test that logs are collected and stored in Loki."""
        # Record start time
        start_time = datetime.utcnow()

        # Generate some logs
        service = KeyVaultService()
        await service.get_secret("test_secret")
        await service.set_secret("test_secret", "value")

        # Wait a moment for logs to be collected
        await asyncio.sleep(2)

        # Query Loki for the logs
        end_time = datetime.utcnow()
        result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend"}',
            start_time,
            end_time
        )

        # Verify logs were collected
        assert result['status'] == 'success'
        assert len(result['data']['result']) > 0

    async def test_log_attributes_in_loki(self, loki_client):
        """Test that structured log attributes are preserved in Loki."""
        start_time = datetime.utcnow()

        # Generate a log with specific attributes
        service = CleanupService(None, None)
        try:
            await service._perform_cleanup()
        except:
            pass

        await asyncio.sleep(2)

        # Query Loki for error logs with attributes
        end_time = datetime.utcnow()
        result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend"} |= "error"',
            start_time,
            end_time
        )

        # Verify log attributes
        assert result['status'] == 'success'
        logs = result['data']['result']
        assert len(logs) > 0

        # Find our error log
        error_log = None
        for stream in logs:
            for value in stream['values']:
                try:
                    log_data = json.loads(value[1])
                    if 'attributes' in log_data and 'error' in log_data['attributes']:
                        error_log = log_data
                        break
                except json.JSONDecodeError:
                    continue
            if error_log:
                break

        assert error_log is not None
        assert 'attributes' in error_log
        assert 'error' in error_log['attributes']

    async def test_trace_correlation(self, loki_client):
        """Test that logs are correlated with traces."""
        start_time = datetime.utcnow()

        # Generate logs within a trace
        storage = StorageService()
        # StorageService operations automatically create spans
        await storage.get_bucket_size("test_bucket")

        await asyncio.sleep(2)

        # Query Loki for logs with trace IDs
        end_time = datetime.utcnow()
        result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend"} | json | trace_id != ""',
            start_time,
            end_time
        )

        # Verify trace correlation
        assert result['status'] == 'success'
        assert len(result['data']['result']) > 0

    async def test_log_levels(self, loki_client):
        """Test that different log levels are properly indexed."""
        start_time = datetime.utcnow()

        # Generate logs at different levels
        service = KeyVaultService()
        # This will generate INFO and WARN logs
        await service.get_secret("nonexistent_secret")

        await asyncio.sleep(2)

        # Query for specific log levels
        end_time = datetime.utcnow()
        
        # Check WARN logs
        warn_result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend", level="WARN"}',
            start_time,
            end_time
        )
        assert warn_result['status'] == 'success'
        assert len(warn_result['data']['result']) > 0

        # Check INFO logs
        info_result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend", level="INFO"}',
            start_time,
            end_time
        )
        assert info_result['status'] == 'success'
        assert len(info_result['data']['result']) > 0

    async def test_service_specific_logs(self, loki_client):
        """Test that logs from different services are properly labeled."""
        start_time = datetime.utcnow()

        # Generate logs from different services
        keyvault = KeyVaultService()
        await keyvault.get_secret("test")

        storage = StorageService()
        await storage.get_bucket_size("test")

        await asyncio.sleep(2)

        # Query for service-specific logs
        end_time = datetime.utcnow()

        # Check KeyVault logs
        keyvault_result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend", service="keyvault"}',
            start_time,
            end_time
        )
        assert keyvault_result['status'] == 'success'
        assert len(keyvault_result['data']['result']) > 0

        # Check Storage logs
        storage_result = await self.query_loki(
            loki_client,
            '{app="transcribo-backend", service="storage"}',
            start_time,
            end_time
        )
        assert storage_result['status'] == 'success'
        assert len(storage_result['data']['result']) > 0
