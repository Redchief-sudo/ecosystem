"""
Trace Context for Distributed Tracing
======================================

Provides request tracing across the entire trading pipeline.
"""

import time
from dataclasses import dataclass, field
from typing import Dict
from uuid import uuid4


@dataclass
class TraceContext:
    """
    Trace context for end-to-end request tracking.
    
    Propagated through: TokenCandidate → TradeOpportunity → ApprovedOrder → ExecutionReport
    """
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    parent_span_id: str = ""
    spans: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, any] = field(default_factory=dict)
    
    def start_span(self, name: str) -> None:
        """Start timing a named span."""
        self.spans[f"{name}_start"] = time.time()
    
    def end_span(self, name: str) -> float:
        """End timing a span and return duration in seconds."""
        start_key = f"{name}_start"
        duration_key = f"{name}_duration"
        
        start_time = self.spans.get(start_key)
        if start_time is None:
            return 0.0
        
        duration = time.time() - start_time
        self.spans[duration_key] = duration
        return duration
    
    def get_span_duration(self, name: str) -> float:
        """Get duration of a completed span."""
        return self.spans.get(f"{name}_duration", 0.0)
    
    def get_total_latency(self) -> float:
        """Calculate total end-to-end latency."""
        if not self.spans:
            return 0.0
        
        start_times = [v for k, v in self.spans.items() if k.endswith("_start")]
        duration_times = [v for k, v in self.spans.items() if k.endswith("_duration")]
        
        if not start_times:
            return 0.0
        
        earliest_start = min(start_times)
        latest_end = earliest_start + sum(duration_times)
        
        return latest_end - earliest_start
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging/serialization."""
        return {
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "total_latency_ms": self.get_total_latency() * 1000,
            "spans": {
                k.replace("_duration", ""): v * 1000
                for k, v in self.spans.items()
                if k.endswith("_duration")
            },
            "metadata": self.metadata
        }
