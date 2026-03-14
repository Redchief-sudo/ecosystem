"""
Prometheus Metrics Exporter
Exports metrics in Prometheus format for monitoring.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from aiohttp import web

logger = logging.getLogger(__name__)


class PrometheusExporter:
    """
    Exports metrics in Prometheus format.
    """
    
    def __init__(
        self,
        metrics_collector: Any,
        portfolio_manager: Any,
        state_manager: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        self.metrics = metrics_collector
        self.portfolio = portfolio_manager
        self.state = state_manager
        self.config = config or {}
        
        self.port = self.config.get("port", 9090)
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
    
    async def start(self):
        """Start the Prometheus exporter with port-conflict resilience."""
        self._app = web.Application()
        self._app.router.add_get('/metrics', self._metrics_handler)
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        # Try the configured port, then fall back to alternatives
        for port in [self.port, self.port + 1, self.port + 2, 0]:
            try:
                self._site = web.TCPSite(self._runner, '0.0.0.0', port)
                await self._site.start()
                self.port = port
                logger.info(f"Prometheus exporter started on port {self.port}")
                return
            except OSError as e:
                if port == 0:
                    raise
                logger.warning(f"Port {port} in use, trying next: {e}")
        
        logger.error("Prometheus exporter failed to start on any port")
    
    async def stop(self):
        """Stop the Prometheus exporter."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        logger.info("Prometheus exporter stopped")
    
    async def _metrics_handler(self, request: web.Request) -> web.Response:
        """Handle metrics request."""
        metrics_text = self._generate_metrics()
        return web.Response(
            text=metrics_text,
            content_type='text/plain; version=0.0.4'
        )
    
    def _generate_metrics(self) -> str:
        """Generate Prometheus-formatted metrics."""
        lines = []
        
        # System state
        state_value = 1 if self.state and hasattr(self.state, 'get_state') else 0
        lines.append(f'system_state{{state="live"}} {state_value}')
        
        # Portfolio metrics
        if self.portfolio and hasattr(self.portfolio, 'get_portfolio_state'):
            portfolio = self.portfolio.get_portfolio_state()
            lines.append(f'portfolio_positions {portfolio.get("positions", 0)}')
            lines.append(f'portfolio_exposure {portfolio.get("total_exposure", 0)}')
            lines.append(f'portfolio_unrealized_pnl {portfolio.get("total_unrealized_pnl", 0)}')
            lines.append(f'portfolio_realized_pnl {portfolio.get("total_realized_pnl", 0)}')
        
        # Metrics collector stats
        if self.metrics and hasattr(self.metrics, 'get_summary'):
            summary = self.metrics.get_summary()
            lines.append(f'trades_total {summary.get("stats", {}).get("total_trades", 0)}')
            lines.append(f'trades_successful {summary.get("stats", {}).get("successful_trades", 0)}')
            lines.append(f'trades_failed {summary.get("stats", {}).get("failed_trades", 0)}')
        
        return '\n'.join(lines)


class MetricsDashboard:
    """
    Web dashboard for metrics visualization.
    """
    
    def __init__(
        self,
        metrics_collector: Any,
        portfolio_manager: Any,
        config: Optional[Dict[str, Any]] = None
    ):
        self.metrics = metrics_collector
        self.portfolio = portfolio_manager
        self.config = config or {}
        
        self.port = self.config.get("port", 8080)
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
    
    async def start(self):
        """Start the metrics dashboard."""
        self._app = web.Application()
        self._app.router.add_get('/', self._dashboard_handler)
        
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        
        self._site = web.TCPSite(self._runner, '0.0.0.0', self.port)
        await self._site.start()
        
        logger.info(f"Metrics dashboard started on port {self.port}")
    
    async def stop(self):
        """Stop the metrics dashboard."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        logger.info("Metrics dashboard stopped")
    
    async def _dashboard_handler(self, request: web.Request) -> web.Response:
        """Handle dashboard request."""
        html = self._generate_dashboard()
        return web.Response(
            text=html,
            content_type='text/html'
        )
    
    def _generate_dashboard(self) -> str:
        """Generate simple HTML dashboard."""
        portfolio_state = {}
        if self.portfolio and hasattr(self.portfolio, 'get_portfolio_state'):
            portfolio_state = self.portfolio.get_portfolio_state()
        
        metrics_summary = {}
        if self.metrics and hasattr(self.metrics, 'get_summary'):
            metrics_summary = self.metrics.get_summary()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Trading System Dashboard</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .metric {{ margin: 10px 0; padding: 10px; background: #f0f0f0; }}
                .value {{ font-size: 24px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Trading System Dashboard</h1>
            
            <div class="metric">
                <div>Positions</div>
                <div class="value">{portfolio_state.get('positions', 0)}</div>
            </div>
            
            <div class="metric">
                <div>Total Exposure</div>
                <div class="value">${portfolio_state.get('total_exposure', 0):.2f}</div>
            </div>
            
            <div class="metric">
                <div>Realized PnL</div>
                <div class="value">${portfolio_state.get('total_realized_pnl', 0):.2f}</div>
            </div>
            
            <div class="metric">
                <div>Total Trades</div>
                <div class="value">{metrics_summary.get('stats', {}).get('total_trades', 0)}</div>
            </div>
        </body>
        </html>
        """
