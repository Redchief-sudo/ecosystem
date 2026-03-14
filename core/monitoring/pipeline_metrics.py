"""
Pipeline metrics collection and monitoring.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
import asyncio
import logging
import time

logger = logging.getLogger("pipeline.metrics")

@dataclass
class ScannerMetrics:
    """Tracks metrics for a single scanner."""
    scanner_name: str
    chain: str
    total_scans: int = 0
    successful_scans: int = 0
    failed_scans: int = 0
    tokens_discovered: int = 0
    tokens_skipped: int = 0
    last_scan_time: Optional[float] = None
    scan_durations: List[float] = field(default_factory=list)
    errors: Dict[str, int] = field(default_factory=dict)

    def record_scan(self, success: bool, duration: float, tokens_found: int = 0, tokens_skipped: int = 0, error: Optional[Exception] = None):
        self.total_scans += 1
        if success:
            self.successful_scans += 1
            self.tokens_discovered += tokens_found
            self.tokens_skipped += tokens_skipped
        else:
            self.failed_scans += 1
            if error:
                error_name = error.__class__.__name__
                self.errors[error_name] = self.errors.get(error_name, 0) + 1
        
        self.scan_durations.append(duration)
        self.last_scan_time = time.time()
        # Keep only last 100 durations for stats
        if len(self.scan_durations) > 100:
            self.scan_durations = self.scan_durations[-100:]

@dataclass
class QueueMetrics:
    """Tracks metrics for a queue."""
    queue_name: str
    chain: str
    enqueued: int = 0
    dequeued: int = 0
    current_size: int = 0
    max_size: int = 0
    avg_process_time: float = 0.0
    last_processed: Optional[float] = None
    processing_times: List[float] = field(default_factory=list)

    def record_enqueue(self, count: int = 1):
        self.enqueued += count
        self.current_size += count
        self.max_size = max(self.max_size, self.current_size)

    def record_dequeue(self, count: int = 1, process_time: Optional[float] = None):
        self.dequeued += count
        self.current_size = max(0, self.current_size - count)
        if process_time is not None:
            self.processing_times.append(process_time)
            if len(self.processing_times) > 100:
                self.processing_times = self.processing_times[-100:]
            self.avg_process_time = sum(self.processing_times) / len(self.processing_times)
        self.last_processed = time.time()

class PipelineMonitor:
    """Central monitoring for the entire pipeline."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.scanners: Dict[str, Dict[str, ScannerMetrics]] = {}  # scanner_name -> chain -> metrics
        self.queues: Dict[str, QueueMetrics] = {}  # queue_name -> metrics
        self.chain_status: Dict[str, Dict[str, Any]] = {}  # chain -> status
        self.start_time = time.time()
        self._lock = asyncio.Lock()
        self._initialized = True

    async def record_scan(
        self,
        scanner_name: str,
        chain: str,
        success: bool,
        duration: float,
        tokens_found: int = 0,
        tokens_skipped: int = 0,
        error: Optional[Exception] = None
    ):
        async with self._lock:
            if scanner_name not in self.scanners:
                self.scanners[scanner_name] = {}
            if chain not in self.scanners[scanner_name]:
                self.scanners[scanner_name][chain] = ScannerMetrics(scanner_name, chain)
            
            self.scanners[scanner_name][chain].record_scan(
                success, duration, tokens_found, tokens_skipped, error
            )

    async def record_enqueue(self, queue_name: str, chain: str, count: int = 1):
        async with self._lock:
            if queue_name not in self.queues:
                self.queues[queue_name] = QueueMetrics(queue_name, chain)
            self.queues[queue_name].record_enqueue(count)

    async def record_dequeue(self, queue_name: str, chain: str, count: int = 1, process_time: Optional[float] = None):
        async with self._lock:
            if queue_name in self.queues:
                self.queues[queue_name].record_dequeue(count, process_time)

    async def update_chain_status(self, chain: str, status: Dict[str, Any]):
        async with self._lock:
            self.chain_status[chain] = {
                **self.chain_status.get(chain, {}),
                **status,
                "last_updated": time.time()
            }

    async def get_metrics(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "uptime": time.time() - self.start_time,
                "scanners": {
                    scanner_name: {
                        chain: self._serialize_scanner_metrics(metrics)
                        for chain, metrics in chains.items()
                    }
                    for scanner_name, chains in self.scanners.items()
                },
                "queues": {
                    name: self._serialize_queue_metrics(metrics)
                    for name, metrics in self.queues.items()
                },
                "chains": self.chain_status
            }
    
    def _serialize_scanner_metrics(self, metrics: ScannerMetrics) -> Dict[str, Any]:
        durations = metrics.scan_durations
        avg_duration = sum(durations) / len(durations) if durations else 0
        return {
            "scans": metrics.total_scans,
            "success_rate": metrics.successful_scans / metrics.total_scans if metrics.total_scans > 0 else 0,
            "tokens_discovered": metrics.tokens_discovered,
            "tokens_skipped": metrics.tokens_skipped,
            "avg_scan_duration": avg_duration,
            "last_scan": metrics.last_scan_time,
            "errors": metrics.errors
        }
    
    def _serialize_queue_metrics(self, metrics: QueueMetrics) -> Dict[str, Any]:
        return {
            "enqueued": metrics.enqueued,
            "dequeued": metrics.dequeued,
            "current_size": metrics.current_size,
            "max_size": metrics.max_size,
            "avg_process_time": metrics.avg_process_time,
            "last_processed": metrics.last_processed
        }

# Global instance
pipeline_monitor = PipelineMonitor()

async def log_pipeline_status(interval: int = 5):
    """Background task to log pipeline status."""
    while True:
        metrics = await pipeline_monitor.get_metrics()
        logger = logging.getLogger("pipeline.monitor")
        
        # Log scanner status
        for scanner, chains in metrics["scanners"].items():
            for chain, stats in chains.items():
                logger.info(
                    f"Scanner {scanner}@{chain}: "
                    f"scans={stats['scans']} "
                    f"success={stats['success_rate']:.1%} "
                    f"tokens={stats['tokens_discovered']} "
                    f"skipped={stats['tokens_skipped']} "
                    f"avg_time={stats['avg_scan_duration']:.2f}s"
                )
        
        # Log queue status
        for queue_name, stats in metrics["queues"].items():
            logger.info(
                f"Queue {queue_name}: "
                f"size={stats['current_size']}/{stats['max_size']} "
                f"processed={stats['dequeued']} "
                f"avg_time={stats['avg_process_time']:.4f}s"
            )
        
        # Log chain status
        for chain, status in metrics["chains"].items():
            logger.info(f"Chain {chain} status: {status}")
        
        await asyncio.sleep(interval)
