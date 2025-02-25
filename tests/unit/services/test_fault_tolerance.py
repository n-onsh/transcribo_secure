"""Tests for fault tolerance service."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

from backend.src.services.fault_tolerance import FaultToleranceService
from backend.src.services.job_distribution import JobDistributor

@pytest.fixture
def mock_db():
    """Create mock database service"""
    db = Mock()
    db.pool = Mock()
    db.pool.acquire = AsyncMock()
    return db

@pytest.fixture
def mock_distributor():
    """Create mock job distributor"""
    distributor = Mock(spec=JobDistributor)
    distributor.unregister_worker = AsyncMock()
    return distributor

@pytest.fixture
async def fault_tolerance(mock_db, mock_distributor):
    """Create fault tolerance service with mocked dependencies"""
    service = FaultToleranceService(
        db=mock_db,
        distributor=mock_distributor,
        health_check_interval=1,  # 1 second for tests
        health_check_timeout=1,  # 1 second for tests
        failure_threshold=2,
        recovery_threshold=2,
        failover_delay=1  # 1 second for tests
    )
    await service.initialize()
    return service

@pytest.mark.asyncio
async def test_register_worker(fault_tolerance):
    """Test worker registration"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    assert worker_id in fault_tolerance.worker_heartbeats
    assert worker_id in fault_tolerance.worker_failures
    assert worker_id in fault_tolerance.worker_recoveries
    assert fault_tolerance.worker_failures[worker_id] == 0
    assert fault_tolerance.worker_recoveries[worker_id] == 0

@pytest.mark.asyncio
async def test_unregister_worker(fault_tolerance):
    """Test worker unregistration"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    await fault_tolerance.unregister_worker(worker_id)
    
    assert worker_id not in fault_tolerance.worker_heartbeats
    assert worker_id not in fault_tolerance.worker_failures
    assert worker_id not in fault_tolerance.worker_recoveries
    assert worker_id not in fault_tolerance.failed_workers
    assert worker_id not in fault_tolerance.recovering_workers

@pytest.mark.asyncio
async def test_heartbeat(fault_tolerance):
    """Test worker heartbeat"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    # Record heartbeat
    initial_time = fault_tolerance.worker_heartbeats[worker_id]
    await asyncio.sleep(0.1)  # Small delay
    await fault_tolerance.heartbeat(worker_id)
    
    # Verify heartbeat updated
    assert fault_tolerance.worker_heartbeats[worker_id] > initial_time

@pytest.mark.asyncio
async def test_worker_failure_detection(fault_tolerance):
    """Test worker failure detection"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    # Wait for health check timeout
    await asyncio.sleep(1.1)
    
    # Wait for failure threshold
    await asyncio.sleep(1.1)
    
    # Verify worker marked as failed
    assert worker_id in fault_tolerance.failed_workers
    assert fault_tolerance.worker_failures[worker_id] >= 2
    fault_tolerance.distributor.unregister_worker.assert_called_once_with(worker_id)

@pytest.mark.asyncio
async def test_worker_recovery(fault_tolerance):
    """Test worker recovery"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    # Mark worker as failed
    fault_tolerance.failed_workers.add(worker_id)
    
    # Send heartbeats for recovery
    for _ in range(2):
        await fault_tolerance.heartbeat(worker_id)
        await asyncio.sleep(0.1)
    
    # Wait for recovery check
    await asyncio.sleep(1.1)
    
    # Verify worker recovered
    assert worker_id not in fault_tolerance.failed_workers
    assert worker_id not in fault_tolerance.recovering_workers
    assert fault_tolerance.worker_failures[worker_id] == 0
    assert fault_tolerance.worker_recoveries[worker_id] == 0

@pytest.mark.asyncio
async def test_worker_health_status(fault_tolerance):
    """Test worker health status reporting"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    # Check initial status
    status = await fault_tolerance.get_worker_health(worker_id)
    assert status["status"] == "healthy"
    assert status["failures"] == 0
    assert status["recoveries"] == 0
    
    # Mark worker as failed
    fault_tolerance.failed_workers.add(worker_id)
    
    # Check failed status
    status = await fault_tolerance.get_worker_health(worker_id)
    assert status["status"] == "failed"
    
    # Start recovery
    fault_tolerance.recovering_workers.add(worker_id)
    
    # Check recovering status
    status = await fault_tolerance.get_worker_health(worker_id)
    assert status["status"] == "recovering"

@pytest.mark.asyncio
async def test_system_health_status(fault_tolerance):
    """Test system health status reporting"""
    # Register multiple workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await fault_tolerance.register_worker(worker_id)
    
    # Check initial status
    status = await fault_tolerance.get_system_health()
    assert status["total_workers"] == 3
    assert status["healthy_workers"] == 3
    assert status["failed_workers"] == 0
    assert status["recovering_workers"] == 0
    assert status["status"] == "healthy"
    
    # Mark one worker as failed
    fault_tolerance.failed_workers.add("worker1")
    
    # Mark one worker as recovering
    fault_tolerance.recovering_workers.add("worker2")
    
    # Check updated status
    status = await fault_tolerance.get_system_health()
    assert status["total_workers"] == 3
    assert status["healthy_workers"] == 1
    assert status["failed_workers"] == 1
    assert status["recovering_workers"] == 1
    assert status["status"] == "healthy"  # Still healthy with one worker
    
    # Mark all workers as failed
    for worker_id in workers:
        fault_tolerance.failed_workers.add(worker_id)
        fault_tolerance.recovering_workers.discard(worker_id)
    
    # Check degraded status
    status = await fault_tolerance.get_system_health()
    assert status["healthy_workers"] == 0
    assert status["status"] == "degraded"

@pytest.mark.asyncio
async def test_failover_delay(fault_tolerance):
    """Test failover delay before recovery"""
    worker_id = "test-worker"
    await fault_tolerance.register_worker(worker_id)
    
    # Mark worker as failed
    start_time = datetime.utcnow()
    await fault_tolerance._handle_worker_failure(worker_id)
    
    # Try immediate recovery
    await fault_tolerance.heartbeat(worker_id)
    
    # Verify still marked as failed
    assert worker_id in fault_tolerance.failed_workers
    
    # Wait for failover delay
    await asyncio.sleep(1.1)
    
    # Now recovery should work
    await fault_tolerance.heartbeat(worker_id)
    assert worker_id in fault_tolerance.recovering_workers

@pytest.mark.asyncio
async def test_multiple_failures(fault_tolerance):
    """Test handling multiple worker failures"""
    # Register multiple workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await fault_tolerance.register_worker(worker_id)
    
    # Fail workers one by one
    for worker_id in workers:
        await fault_tolerance._handle_worker_failure(worker_id)
        await asyncio.sleep(0.1)
    
    # Verify all workers failed
    assert len(fault_tolerance.failed_workers) == 3
    assert fault_tolerance.distributor.unregister_worker.call_count == 3
    
    # Start recovery
    for worker_id in workers:
        await fault_tolerance.heartbeat(worker_id)
    
    # Verify all in recovery
    assert len(fault_tolerance.recovering_workers) == 3

@pytest.mark.asyncio
async def test_partial_recovery(fault_tolerance):
    """Test partial system recovery"""
    # Register multiple workers
    workers = ["worker1", "worker2", "worker3"]
    for worker_id in workers:
        await fault_tolerance.register_worker(worker_id)
        fault_tolerance.failed_workers.add(worker_id)
    
    # Recover some workers
    recovered_workers = workers[:2]
    for worker_id in recovered_workers:
        for _ in range(2):  # Meet recovery threshold
            await fault_tolerance.heartbeat(worker_id)
            await asyncio.sleep(0.1)
    
    # Wait for recovery check
    await asyncio.sleep(1.1)
    
    # Verify partial recovery
    status = await fault_tolerance.get_system_health()
    assert status["healthy_workers"] == 2
    assert status["failed_workers"] == 1
    assert status["status"] == "healthy"  # System still healthy
