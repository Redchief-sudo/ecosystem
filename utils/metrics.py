"""Metrics collection for the trading bot."""
import time
from typing import Any, Dict, Optional

from prometheus_client import Counter, Gauge, Histogram, start_http_server


class MetricsCollector:
    """Collects and exposes metrics for the trading bot."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MetricsCollector, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        # Initialize metrics
        self.scans_total = Counter(
            'trading_bot_scans_total',
            'Total number of scans performed',
            ['chain', 'scanner']
        )
        
        self.tokens_found = Counter(
            'trading_bot_tokens_found_total',
            'Total number of tokens found',
            ['chain', 'scanner']
        )
        
        self.trades_executed = Counter(
            'trading_bot_trades_executed_total',
            'Total number of trades executed',
            ['chain', 'side']
        )
        
        self.trade_amount = Gauge(
            'trading_bot_trade_amount',
            'Amount of tokens traded',
            ['chain', 'token', 'side']
        )
        
        self.trade_profit = Gauge(
            'trading_bot_trade_profit',
            'Profit/loss from trades',
            ['chain', 'token']
        )
        
        self.scan_duration = Histogram(
            'trading_bot_scan_duration_seconds',
            'Time spent scanning for tokens',
            ['chain', 'scanner'],
            buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60]
        )
        
        self.rpc_errors = Counter(
            'trading_bot_rpc_errors_total',
            'Total number of RPC errors',
            ['chain', 'method']
        )
        
        self.errors = Counter(
            'trading_bot_errors_total',
            'Total number of errors',
            ['error_type']
        )
        
        self._initialized = True
    
    def start_metrics_server(self, port: int = 8000) -> None:
        """Start the metrics HTTP server."""
        start_http_server(port)
    
    def record_scan(self, chain: str, scanner: str, tokens_found: int = 0) -> None:
        """Record a scan operation."""
        self.scans_total.labels(chain=chain, scanner=scanner).inc()
        if tokens_found > 0:
            self.tokens_found.labels(chain=chain, scanner=scanner).inc(tokens_found)
    
    def record_trade(
        self,
        chain: str,
        token: str,
        side: str,
        amount: float,
        profit: Optional[float] = None
    ) -> None:
        """Record a trade execution."""
        self.trades_executed.labels(chain=chain, side=side).inc()
        self.trade_amount.labels(chain=chain, token=token, side=side).set(amount)
        
        if profit is not None:
            self.trade_profit.labels(chain=chain, token=token).set(profit)
    
    def record_rpc_error(self, chain: str, method: str) -> None:
        """Record an RPC error."""
        self.rpc_errors.labels(chain=chain, method=method).inc()
        
    def record_error(self, error_type: str) -> None:
        """Record an error occurrence."""
        self.errors.labels(error_type=error_type).inc()
    
    def record_system_health(self, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        """Record system health status."""
        # This could be expanded to track health metrics over time
        # For now, just log the health status
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"System health: {status}")
        if details:
            logger.debug(f"Health details: {details}")

# Global instance
metrics = MetricsCollector()
