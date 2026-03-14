"""Protocol definitions for type checking and interface validation."""
from typing import Protocol, runtime_checkable, Dict, List, Any, Optional, AsyncIterator
from dataclasses import dataclass

@runtime_checkable
class NetworkManagerProtocol(Protocol):
    """Protocol for network manager implementations."""
    async def is_chain_compatible_with_scanner(self, chain: str, scanner: str) -> bool:
        """Check if a chain is compatible with a scanner."""
        ...

@runtime_checkable
class MemoryStoreProtocol(Protocol):
    """Protocol for memory store implementations."""
    async def get_token_availability_status(self) -> Dict[str, Any]:
        """Get token availability status."""
        ...
    
    async def is_connected(self) -> bool:
        """Check if the memory store is connected."""
        ...

@runtime_checkable
class MetricsProtocol(Protocol):
    """Protocol for metrics collection."""
    def update_scan_metrics(self, scanner: str, chain: str, success: bool, duration: float):
        """Update scan metrics."""
        ...

@runtime_checkable
class ScannerProtocol(Protocol):
    """Protocol for scanner implementations."""
    async def scan(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """Perform the scanning operation."""
        ...
    
    async def initialize(self) -> None:
        """Initialize scanner resources."""
        ...
    
    async def cleanup(self) -> None:
        """Clean up scanner resources."""
        ...

@dataclass
class ScannerHealth:
    """Health status of a scanner."""
    failures: int = 0
    last_failure: Optional[float] = None
    last_success: Optional[float] = None
    active: bool = True

@dataclass
class ScanResult:
    """Result of a scan operation."""
    success: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None
    scanner: Optional[str] = None
    chain: Optional[str] = None
