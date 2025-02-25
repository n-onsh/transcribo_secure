"""Fault tolerance service for transcriber workers."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import uuid

from opentelemetry import trace, logs
from opentelemetry.logs import Severity

from ..models.job import Job, JobStatus
from ..services.database import DatabaseService
from ..services.job_distribution import JobDistributor
from ..utils.metrics import (
    WORKER_HEALTH_STATUS,
    WORKER_RECOVERY_COUNT,
    WORKER_FAILOVER_TIME,
    track_time,
    track_errors,
    update_gauge
)

logger = logs.get_logger(__name__)
tracer = trace.get_tracer(__name__)

class FaultToleranceService:
    """Manages fault tolerance for transcriber workers."""
    
    def __init__(
        self,
        db: DatabaseService,
        distributor: JobDistributor,
        health_check_interval: int = 30,  # seconds
        health_check_timeout: int = 5,  # seconds
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        failover_delay: int = 10  # seconds
    ):
        self.db = db
        self.distributor = distributor
        self.health_check_interval = health_check_interval
        self.health_check_timeout = health_check_timeout
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.failover_delay = failover_delay
        
        # Worker state tracking
        self.worker_heartbeats: Dict[str, datetime] = {}
        self.worker_failures: Dict[str, int] = {}
        self.worker_recoveries: Dict[str, int] = {}
        self.failed_workers: Set[str] = set()
        self.recovering_workers: Set[str] = set()

    async def initialize(self):
        """Initialize fault tolerance service."""
        # Start background tasks
        asyncio.create_task(self._monitor_worker_health())
        asyncio.create_task(self._handle_worker_recovery())
        logger.emit(
            "Fault tolerance service initialized",
            severity=Severity.INFO
        )

    async def register_worker(self, worker_id: str) -> None:
        """Register a new worker for health monitoring."""
        self.worker_heartbeats[worker_id] = datetime.utcnow()
        self.worker_failures[worker_id] = 0
        self.worker_recoveries[worker_id] = 0
        update_gauge(WORKER_HEALTH_STATUS, 1, {"worker_id": worker_id})
        logger.emit(
            "Worker registered for health monitoring",
            severity=Severity.INFO,
            attributes={"worker_id": worker_id}
        )

    async def unregister_worker(self, worker_id: str) -> None:
        """Unregister a worker from health monitoring."""
        self.worker_heartbeats.pop(worker_id, None)
        self.worker_failures.pop(worker_id, None)
        self.worker_recoveries.pop(worker_id, None)
        self.failed_workers.discard(worker_id)
        self.recovering_workers.discard(worker_id)
        update_gauge(WORKER_HEALTH_STATUS, 0, {"worker_id": worker_id})
        logger.emit(
            "Worker unregistered from health monitoring",
            severity=Severity.INFO,
            attributes={"worker_id": worker_id}
        )

    @track_time("worker_heartbeat_duration", {"operation": "heartbeat"})
    @track_errors("worker_heartbeat_errors", {"operation": "heartbeat"})
    async def heartbeat(self, worker_id: str) -> None:
        """Record worker heartbeat."""
        self.worker_heartbeats[worker_id] = datetime.utcnow()
        
        # Check if worker was failed
        if worker_id in self.failed_workers:
            self.recovering_workers.add(worker_id)
            self.worker_recoveries[worker_id] = self.worker_recoveries.get(worker_id, 0) + 1
            WORKER_RECOVERY_COUNT.inc({"worker_id": worker_id})
            logger.emit(
                "Failed worker showing signs of recovery",
                severity=Severity.INFO,
                attributes={"worker_id": worker_id}
            )

    async def _monitor_worker_health(self):
        """Monitor worker health through heartbeats."""
        while True:
            try:
                current_time = datetime.utcnow()
                for worker_id, last_heartbeat in self.worker_heartbeats.items():
                    # Skip workers already marked as failed
                    if worker_id in self.failed_workers:
                        continue
                    
                    # Check heartbeat age
                    age = (current_time - last_heartbeat).total_seconds()
                    if age > self.health_check_timeout:
                        self.worker_failures[worker_id] = self.worker_failures.get(worker_id, 0) + 1
                        
                        # Check failure threshold
                        if self.worker_failures[worker_id] >= self.failure_threshold:
                            await self._handle_worker_failure(worker_id)
                    else:
                        # Reset failure count on good heartbeat
                        self.worker_failures[worker_id] = 0
            
            except Exception as e:
                logger.emit(
                    "Error monitoring worker health",
                    severity=Severity.ERROR,
                    attributes={"error": str(e)}
                )
            
            await asyncio.sleep(self.health_check_interval)

    async def _handle_worker_failure(self, worker_id: str):
        """Handle worker failure."""
        try:
            # Mark worker as failed
            self.failed_workers.add(worker_id)
            update_gauge(WORKER_HEALTH_STATUS, 0, {"worker_id": worker_id})
            
            # Start failover timer
            start_time = datetime.utcnow()
            
            # Release worker's jobs
            await self.distributor.unregister_worker(worker_id)
            
            # Record failover time
            failover_time = (datetime.utcnow() - start_time).total_seconds()
            WORKER_FAILOVER_TIME.observe(failover_time)
            
            logger.emit(
                "Worker failure handled",
                severity=Severity.WARNING,
                attributes={
                    "worker_id": worker_id,
                    "failures": self.worker_failures[worker_id],
                    "failover_time": failover_time
                }
            )
            
            # Wait before allowing recovery
            await asyncio.sleep(self.failover_delay)
            
        except Exception as e:
            logger.emit(
                "Error handling worker failure",
                severity=Severity.ERROR,
                attributes={
                    "error": str(e),
                    "worker_id": worker_id
                }
            )

    async def _handle_worker_recovery(self):
        """Monitor and handle worker recovery."""
        while True:
            try:
                for worker_id in list(self.recovering_workers):
                    # Check recovery threshold
                    if self.worker_recoveries[worker_id] >= self.recovery_threshold:
                        # Worker has recovered
                        self.failed_workers.discard(worker_id)
                        self.recovering_workers.discard(worker_id)
                        self.worker_failures[worker_id] = 0
                        self.worker_recoveries[worker_id] = 0
                        update_gauge(WORKER_HEALTH_STATUS, 1, {"worker_id": worker_id})
                        
                        logger.emit(
                            "Worker recovered",
                            severity=Severity.INFO,
                            attributes={"worker_id": worker_id}
                        )
            
            except Exception as e:
                logger.emit(
                    "Error handling worker recovery",
                    severity=Severity.ERROR,
                    attributes={"error": str(e)}
                )
            
            await asyncio.sleep(self.health_check_interval)

    async def get_worker_health(self, worker_id: str) -> Dict:
        """Get worker health status."""
        return {
            "worker_id": worker_id,
            "last_heartbeat": self.worker_heartbeats.get(worker_id),
            "failures": self.worker_failures.get(worker_id, 0),
            "recoveries": self.worker_recoveries.get(worker_id, 0),
            "status": "failed" if worker_id in self.failed_workers
                     else "recovering" if worker_id in self.recovering_workers
                     else "healthy"
        }

    async def get_system_health(self) -> Dict:
        """Get overall system health status."""
        total_workers = len(self.worker_heartbeats)
        failed_workers = len(self.failed_workers)
        recovering_workers = len(self.recovering_workers)
        healthy_workers = total_workers - failed_workers - recovering_workers
        
        return {
            "total_workers": total_workers,
            "healthy_workers": healthy_workers,
            "failed_workers": failed_workers,
            "recovering_workers": recovering_workers,
            "status": "healthy" if healthy_workers > 0 else "degraded"
        }
