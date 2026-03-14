"""
Metrics Collector
Collects and aggregates system metrics.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    value: float
    timestamp: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """
    Collects and aggregates system metrics.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Configuration
        self.max_history = self.config.get("max_history_points", 1000)
        self.retention_seconds = self.config.get("retention_seconds", 3600)
        
        # Metrics storage
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[MetricPoint]] = {}
        self._execution_history: deque = deque(maxlen=self.max_history)
        
        # Statistics
        self._total_trades = 0
        self._successful_trades = 0
        self._failed_trades = 0
        self._start_time = time.time()
        
        logger.info("MetricsCollector initialized")
    
    def increment_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter metric."""
        key = self._make_key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric."""
        key = self._make_key(name, labels)
        self._gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record a histogram observation."""
        key = self._make_key(name, labels)
        
        if key not in self._histograms:
            self._histograms[key] = []
        
        self._histograms[key].append(MetricPoint(
            value=value,
            timestamp=time.time(),
            labels=labels or {}
        ))
        
        # Clean old points
        cutoff = time.time() - self.retention_seconds
        self._histograms[key] = [
            p for p in self._histograms[key]
            if p.timestamp > cutoff
        ]
    
    def record_execution(self, success: bool, execution_time_ms: float):
        """Record a trade execution."""
        self._total_trades += 1
        
        if success:
            self._successful_trades += 1
        else:
            self._failed_trades += 1
        
        self._execution_history.append({
            "success": success,
            "execution_time_ms": execution_time_ms,
            "timestamp": time.time()
        })
        
        # Record histogram
        self.record_histogram("execution_time_ms", execution_time_ms)
        self.set_gauge("last_execution_time_ms", execution_time_ms)
    
    def record_opportunity_processed(self, success: bool, execution_time_ms: float):
        """Record opportunity processing."""
        self.increment_counter("opportunities_processed", 1, {"success": str(success)})
        self.record_histogram("opportunity_processing_time_ms", execution_time_ms)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        now = time.time()
        uptime = now - self._start_time
        
        # Calculate success rate for last hour
        hour_ago = now - 3600
        recent_executions = [
            e for e in self._execution_history
            if e["timestamp"] > hour_ago
        ]
        
        success_rate = 0.0
        if recent_executions:
            successful = sum(1 for e in recent_executions if e["success"])
            success_rate = successful / len(recent_executions)
        
        return {
            "uptime_seconds": uptime,
            "execution_1h": {
                "total": len(recent_executions),
                "successful": sum(1 for e in recent_executions if e["success"]),
                "failed": sum(1 for e in recent_executions if not e["success"]),
                "success_rate": success_rate
            },
            "stats": {
                "total_trades": self._total_trades,
                "successful_trades": self._successful_trades,
                "failed_trades": self._failed_trades
            },
            "counters": dict(self._counters),
            "gauges": dict(self._gauges)
        }
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create metric key from name and labels."""
        if not labels:
            return name
        
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"
