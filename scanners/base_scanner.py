import abc
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from utils.circuit_breaker import (CircuitBreaker, CircuitBreakerConfig,
                                   CircuitBreakerOpenError)

from .scanned_token import ScannedToken

logger = logging.getLogger(__name__)

class ScannerBase(abc.ABC):
    """Base class for all scanner implementations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        """
        Initialize the scanner with configuration.
        
        Args:
            config: Configuration dictionary
            **kwargs: Additional keyword arguments
        """
        self.config = config or {}
        self.name = self.__class__.__name__
        self.enabled = True
        self.running = True  # Scanners are ready to run by default
        self.last_scan_time: Optional[datetime] = None
        self.scan_count = 0
        self.error_count = 0
        self.last_error: Optional[str] = None
        
        # Circuit breaker for fault tolerance
        circuit_config = CircuitBreakerConfig(
            failure_threshold=self.config.get('circuit_breaker_failures', 5),
            timeout=self.config.get('circuit_breaker_timeout', 60),
            success_threshold=self.config.get('circuit_breaker_success_threshold', 3),
            expected_exception=Exception
        )
        self.circuit_breaker = CircuitBreaker(circuit_config)
        
        logger.info(f"Scanner {self.__class__.__name__} initialized with circuit breaker")
        
    def set_config(self, config: Dict[str, Any]) -> None:
        """
        Update the scanner's configuration.
        
        Args:
            config: New configuration dictionary
        """
        self.config = {**self.config, **config}
    
    async def initialize(self) -> None:
        """Initialize scanner resources. Can be overridden by subclasses."""
        pass
        
    async def cleanup(self) -> None:
        """Clean up scanner resources. Can be overridden by subclasses."""
        pass
    
    @abc.abstractmethod
    async def scan(self, *args, **kwargs) -> List[Dict]:
        """
        Perform the scanning operation. Must be implemented by subclasses.
        
        Returns:
            List of token data dictionaries
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    async def protected_scan(self, *args, **kwargs) -> List[Dict]:
        """
        Protected scan operation with circuit breaker and error handling.
        
        Returns:
            List of token data dictionaries
        """
        try:
            # Use circuit breaker to protect the scan operation
            result = await self.circuit_breaker.call(self.scan, *args, **kwargs)
            self.scan_count += 1
            self.last_scan_time = datetime.now()
            return result
            
        except CircuitBreakerOpenError:
            error_msg = f"Circuit breaker is OPEN - scanner {self.name} temporarily disabled"
            self.last_error = error_msg
            self.error_count += 1
            logger.warning(f"⚠️ {error_msg} (failure count: {self.error_count})")
            return []
        except asyncio.TimeoutError:
            error_msg = f"Scan timeout - scanner {self.name} took too long"
            self.last_error = error_msg
            self.error_count += 1
            logger.error(f"❌ {error_msg}")
            return []
        except Exception as e:
            error_msg = f"Scan failed: {str(e)}"
            self.last_error = error_msg
            self.error_count += 1
            logger.error(f"❌ {self.name} scan error: {error_msg}", exc_info=True)
            # Log additional context if available
            if hasattr(self, 'last_scan_time'):
                logger.debug(f"Last successful scan: {self.last_scan_time}")
            return []
    
    def get_effective_thresholds(self) -> Dict[str, Any]:
        """
        Get the effective thresholds with strict validation - no silent fallbacks.

        Returns:
            Dictionary of threshold values

        Raises:
            ValueError: If required thresholds are not configured
        """
        from utils.validators import FieldValidator

        # Scanner configuration validation - NO AI scoring in scanners
        self.thresholds = {
            'min_liquidity': FieldValidator.require_field(self.config, 'min_liquidity',
                f"Scanner {self.name} requires 'min_liquidity' configuration"),
            'min_volume': FieldValidator.require_field(self.config, 'min_volume',
                f"Scanner {self.name} requires 'min_volume' configuration"),
            'max_age_hours': FieldValidator.require_field(self.config, 'max_age_hours',
                f"Scanner {self.name} requires 'max_age_hours' configuration")
        }

        # Validate threshold values are reasonable
        if self.thresholds['min_liquidity'] <= 0:
            raise ValueError(f"Scanner {self.name}: min_liquidity must be > 0, got {self.thresholds['min_liquidity']}")

        if self.thresholds['min_volume'] <= 0:
            raise ValueError(f"Scanner {self.name}: min_volume must be > 0, got {self.thresholds['min_volume']}")

        if self.thresholds['max_age_hours'] <= 0:
            raise ValueError(f"Scanner {self.name}: max_age_hours must be > 0, got {self.thresholds['max_age_hours']}")

        logger.info(f"✅ Scanner thresholds validated: {self.thresholds}")
        return self.thresholds
    
    def get_scan_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the scanner's activity.
        
        Returns:
            Dictionary with scan statistics
        """
        success_rate = (
            (self.scan_count - self.error_count) / max(self.scan_count, 1)
        )
        
        return {
            "scanner_name": self.name,
            "enabled": self.enabled,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "scan_count": self.scan_count,
            "error_count": self.error_count,
            "success_rate": success_rate,
            "last_error": self.last_error,
            "circuit_breaker": self.circuit_breaker.get_state(),
            "health_status": 'healthy' if success_rate > 0.8 else 'degraded',
            "config": self.config
        }
    
    def reset_circuit_breaker(self):
        """Manually reset the circuit breaker"""
        self.circuit_breaker.reset()
        logger.info(f"Circuit breaker reset for {self.name}")
    
    async def cleanup(self) -> None:
        """
        Clean up scanner resources. Override in subclasses if needed.
        
        This method should be called during shutdown to properly clean up
        any resources like HTTP sessions, database connections, etc.
        """
        # Default implementation - subclasses should override
        logger.debug(f"Cleaning up {self.name}")
        self.running = False
        
    def __str__(self) -> str:
        return f"{self.name}()"
        
    def __repr__(self) -> str:
        return f"<{self.name} enabled={self.enabled} scans={self.scan_count}>"
