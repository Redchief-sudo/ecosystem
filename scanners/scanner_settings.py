"""
Scanner settings configuration class
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ScannerSettings:
    """Configuration settings for scanner operations."""
    
    # Core scanner settings
    concurrent_scans: int = 8
    scan_interval: int = 60
    max_tokens_per_scan: int = 100
    deduplication_window: int = 300
    
    # Health and reliability settings
    health_check_interval: int = 300
    max_failures: int = 3
    circuit_breaker_timeout: int = 600
    
    # Performance settings
    rate_limit_delay: float = 0.5
    rate_limit_window: int = 60
    max_requests_per_window: int = 80
    
    # API timeouts
    api_timeout: int = 30
    connect_timeout: int = 10
    
    # Chain-specific settings
    per_chain_timeout_s: float = 60.0
    per_scanner_timeout_s: float = 30.0
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'ScannerSettings':
        """Create ScannerSettings from configuration dictionary."""
        scanner_cfg = config.get("scanner", {}) if isinstance(config, dict) else {}
        
        return cls(
            concurrent_scans=int(scanner_cfg.get("max_workers", 8)),
            scan_interval=int(scanner_cfg.get("scan_interval", 60)),
            max_tokens_per_scan=int(scanner_cfg.get("max_tokens_per_scan", 100)),
            deduplication_window=int(scanner_cfg.get("deduplication_window", 300)),
            health_check_interval=int(scanner_cfg.get("health_check_interval", 300)),
            max_failures=int(scanner_cfg.get("max_failures", 3)),
            circuit_breaker_timeout=int(scanner_cfg.get("circuit_breaker_timeout", 600)),
            rate_limit_delay=float(scanner_cfg.get("rate_limit_delay", 0.5)),
            rate_limit_window=int(scanner_cfg.get("rate_limit_window", 60)),
            max_requests_per_window=int(scanner_cfg.get("max_requests_per_window", 80)),
            api_timeout=int(scanner_cfg.get("api_timeout", 30)),
            connect_timeout=int(scanner_cfg.get("connect_timeout", 10)),
            per_chain_timeout_s=float(scanner_cfg.get("scan_chain_timeout_s", 60.0)),
            per_scanner_timeout_s=float(scanner_cfg.get("scan_scanner_timeout_s", 30.0))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ScannerSettings to configuration dictionary."""
        return {
            "scanner": {
                "max_workers": self.concurrent_scans,
                "scan_interval": self.scan_interval,
                "max_tokens_per_scan": self.max_tokens_per_scan,
                "deduplication_window": self.deduplication_window,
                "health_check_interval": self.health_check_interval,
                "max_failures": self.max_failures,
                "circuit_breaker_timeout": self.circuit_breaker_timeout,
                "rate_limit_delay": self.rate_limit_delay,
                "rate_limit_window": self.rate_limit_window,
                "max_requests_per_window": self.max_requests_per_window,
                "api_timeout": self.api_timeout,
                "connect_timeout": self.connect_timeout,
                "scan_chain_timeout_s": self.per_chain_timeout_s,
                "scan_scanner_timeout_s": self.per_scanner_timeout_s
            }
        }
