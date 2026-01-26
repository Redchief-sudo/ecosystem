import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict

import psutil

# Set up logger
logger = logging.getLogger(__name__)

# Simple health endpoint without FastAPI
def get_health() -> Dict[str, Any]:
    """Get system health status."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": psutil.cpu_percent(),
        "memory_percent": psutil.virtual_memory().percent
    }

def get_metrics() -> Dict[str, Any]:
    """Get system metrics."""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cpu_percent": psutil.cpu_percent(),
        "memory_usage_mb": memory_info.rss / (1024 * 1024),  # Convert to MB
        "disk_usage": psutil.disk_usage('/')._asdict(),
        "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else None
    }

def get_strategy_metrics(strategy_manager) -> Dict[str, Any]:
    """Get strategy metrics endpoint."""
    try:
        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": strategy_manager.get_metrics(),
            "health": strategy_manager.get_health_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")
