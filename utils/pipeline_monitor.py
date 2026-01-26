"""
Pipeline Monitoring System
==========================
Comprehensive monitoring for the token recovery pipeline.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class PipelineMetrics:
    """Metrics for pipeline components"""
    component_name: str
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    last_operation_time: Optional[datetime] = None
    last_error: Optional[str] = None
    health_status: str = "unknown"
    
    # Latency tracking
    latency_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update_operation(self, success: bool, latency_ms: float, error: Optional[str] = None):
        """Update metrics after an operation"""
        self.total_operations += 1
        self.last_operation_time = datetime.now()
        
        if success:
            self.successful_operations += 1
        else:
            self.failed_operations += 1
            self.last_error = error
        
        # Update latency
        self.latency_history.append(latency_ms)
        self.avg_latency_ms = sum(self.latency_history) / len(self.latency_history)
        
        # Update error rate
        self.error_rate = self.failed_operations / max(self.total_operations, 1)
        
        # Update health status
        if self.error_rate < 0.05:  # Less than 5% error rate
            self.health_status = "healthy"
        elif self.error_rate < 0.15:  # Less than 15% error rate
            self.health_status = "degraded"
        else:
            self.health_status = "unhealthy"

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric: str
    threshold: float
    comparison: str  # "gt", "lt", "eq"
    severity: str    # "info", "warning", "critical"
    enabled: bool = True

class PipelineMonitor:
    """
    Comprehensive pipeline monitoring system.
    
    Features:
    - Real-time metrics collection
    - Component health tracking
    - Alert management
    - Performance analytics
    - Error tracking
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Metrics storage
        self.component_metrics: Dict[str, PipelineMetrics] = {}
        self.global_metrics = {
            'pipeline_start_time': datetime.now(),
            'total_tokens_scanned': 0,
            'total_tokens_normalized': 0,
            'total_tokens_ingested': 0,
            'total_tokens_rejected': 0,
            'pipeline_errors': 0,
            'avg_pipeline_latency_ms': 0.0,
        }
        
        # Alert management
        self.alert_rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_history: List[Dict] = []
        
        # Performance tracking
        self.pipeline_latency_history = deque(maxlen=1000)
        self.throughput_history = deque(maxlen=100)
        
        # Monitoring state
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Initialize default alert rules
        self._initialize_default_alerts()
        
        self.logger.info("PipelineMonitor initialized")

    def _initialize_default_alerts(self):
        """Initialize default alert rules"""
        default_rules = [
            AlertRule("High Error Rate", "error_rate", 0.10, "gt", "warning"),
            AlertRule("Critical Error Rate", "error_rate", 0.25, "gt", "critical"),
            AlertRule("High Latency", "avg_latency_ms", 5000, "gt", "warning"),
            AlertRule("Critical Latency", "avg_latency_ms", 10000, "gt", "critical"),
            AlertRule("Low Success Rate", "success_rate", 0.90, "lt", "warning"),
        ]
        
        self.alert_rules.extend(default_rules)

    def register_component(self, component_name: str) -> PipelineMetrics:
        """Register a pipeline component for monitoring"""
        if component_name not in self.component_metrics:
            self.component_metrics[component_name] = PipelineMetrics(
                component_name=component_name
            )
            self.logger.info(f"Registered component for monitoring: {component_name}")
        
        return self.component_metrics[component_name]

    def record_operation(self, component: str, success: bool, latency_ms: float, 
                        error: Optional[str] = None, tokens_processed: int = 0):
        """Record a pipeline operation"""
        # Get or create component metrics
        metrics = self.register_component(component)
        metrics.update_operation(success, latency_ms, error)
        
        # Update global metrics
        if success:
            if component == "scanner":
                self.global_metrics['total_tokens_scanned'] += tokens_processed
            elif component == "normalizer":
                self.global_metrics['total_tokens_normalized'] += tokens_processed
            elif component == "ingestion":
                self.global_metrics['total_tokens_ingested'] += tokens_processed
        else:
            self.global_metrics['pipeline_errors'] += 1
        
        # Update pipeline latency
        self.pipeline_latency_history.append(latency_ms)
        self.global_metrics['avg_pipeline_latency_ms'] = (
            sum(self.pipeline_latency_history) / len(self.pipeline_latency_history)
        )
        
        # Check alerts
        self._check_alerts(component, metrics)

    def _check_alerts(self, component: str, metrics: PipelineMetrics):
        """Check if any alert rules are triggered"""
        for rule in self.alert_rules:
            if not rule.enabled:
                continue
            
            # Get metric value
            if rule.metric == "error_rate":
                value = metrics.error_rate
            elif rule.metric == "avg_latency_ms":
                value = metrics.avg_latency_ms
            elif rule.metric == "success_rate":
                value = 1.0 - metrics.error_rate
            else:
                continue
            
            # Check threshold
            triggered = False
            if rule.comparison == "gt" and value > rule.threshold:
                triggered = True
            elif rule.comparison == "lt" and value < rule.threshold:
                triggered = True
            elif rule.comparison == "eq" and abs(value - rule.threshold) < 0.001:
                triggered = True
            
            if triggered:
                self._trigger_alert(rule, component, value)

    def _trigger_alert(self, rule: AlertRule, component: str, value: float):
        """Trigger an alert"""
        alert_id = f"{rule.name}_{component}"
        current_time = datetime.now()
        
        # Check if alert is already active
        if alert_id in self.active_alerts:
            # Check if we should suppress duplicate alerts
            last_triggered = self.active_alerts[alert_id]['triggered_at']
            if (current_time - last_triggered).total_seconds() < 300:  # 5 minutes
                return  # Suppress duplicate
        
        # Create alert
        alert = {
            'alert_id': alert_id,
            'rule_name': rule.name,
            'component': component,
            'severity': rule.severity,
            'metric': rule.metric,
            'value': value,
            'threshold': rule.threshold,
            'triggered_at': current_time.isoformat(),
            'status': 'active'
        }
        
        # Store active alert
        self.active_alerts[alert_id] = alert
        
        # Add to history
        self.alert_history.append(alert)
        
        # Log alert
        self.logger.warning(
            f"ALERT [{rule.severity.upper()}] {rule.name}: "
            f"{component} {rule.metric}={value:.3f} (threshold: {rule.threshold})"
        )
        
        # Send notification (if configured)
        self._send_alert_notification(alert)

    def _send_alert_notification(self, alert: Dict):
        """Send alert notification (placeholder for future implementation)"""
        # This could integrate with Slack, email, PagerDuty, etc.
        pass

    async def start_monitoring(self, interval: int = 60):
        """Start continuous monitoring"""
        if self.is_monitoring:
            self.logger.warning("Monitoring already started")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval))
        self.logger.info(f"Pipeline monitoring started (interval: {interval}s)")

    async def stop_monitoring(self):
        """Stop continuous monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Pipeline monitoring stopped")

    async def _monitoring_loop(self, interval: int):
        """Main monitoring loop"""
        while self.is_monitoring:
            try:
                await self._generate_periodic_report()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(interval)

    async def _generate_periodic_report(self):
        """Generate periodic monitoring report"""
        report = self.get_comprehensive_report()
        
        # Log summary
        self.logger.info(
            f"PIPELINE STATUS: "
            f"Components: {len(self.component_metrics)} | "
            f"Active Alerts: {len(self.active_alerts)} | "
            f"Tokens Scanned: {self.global_metrics['total_tokens_scanned']} | "
            f"Error Rate: {self.global_metrics['pipeline_errors'] / max(sum(self.global_metrics.values()), 1):.2%}"
        )
        
        # Log unhealthy components
        unhealthy = [
            name for name, metrics in self.component_metrics.items()
            if metrics.health_status == "unhealthy"
        ]
        if unhealthy:
            self.logger.warning(f"Unhealthy components: {unhealthy}")

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Get comprehensive monitoring report"""
        # Component health summary
        component_health = {}
        for name, metrics in self.component_metrics.items():
            component_health[name] = {
                'health_status': metrics.health_status,
                'success_rate': 1.0 - metrics.error_rate,
                'avg_latency_ms': metrics.avg_latency_ms,
                'total_operations': metrics.total_operations,
                'last_error': metrics.last_error
            }
        
        # Alert summary
        alert_summary = {
            'active_alerts': len(self.active_alerts),
            'total_alerts': len(self.alert_history),
            'critical_alerts': sum(1 for alert in self.active_alerts.values() 
                                 if alert['severity'] == 'critical'),
            'warning_alerts': sum(1 for alert in self.active_alerts.values() 
                                if alert['severity'] == 'warning')
        }
        
        # Pipeline performance
        uptime = datetime.now() - self.global_metrics['pipeline_start_time']
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': uptime.total_seconds(),
            'global_metrics': self.global_metrics.copy(),
            'component_health': component_health,
            'alert_summary': alert_summary,
            'performance': {
                'avg_pipeline_latency_ms': self.global_metrics['avg_pipeline_latency_ms'],
                'throughput_tokens_per_minute': self._calculate_throughput(),
                'pipeline_efficiency': self._calculate_efficiency()
            }
        }

    def _calculate_throughput(self) -> float:
        """Calculate current throughput (tokens per minute)"""
        if len(self.throughput_history) < 2:
            return 0.0
        
        # Simple throughput calculation
        recent_scans = self.global_metrics['total_tokens_scanned']
        uptime_minutes = (datetime.now() - self.global_metrics['pipeline_start_time']).total_seconds() / 60
        
        return recent_scans / max(uptime_minutes, 1)

    def _calculate_efficiency(self) -> float:
        """Calculate pipeline efficiency (successful tokens / total tokens)"""
        total = (self.global_metrics['total_tokens_scanned'] + 
                self.global_metrics['pipeline_errors'])
        
        if total == 0:
            return 1.0
        
        successful = self.global_metrics['total_tokens_scanned']
        return successful / total

    def export_metrics(self, filepath: str):
        """Export metrics to JSON file"""
        report = self.get_comprehensive_report()
        
        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            self.logger.info(f"Metrics exported to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to export metrics: {e}")

    def get_component_health(self, component_name: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific component"""
        metrics = self.component_metrics.get(component_name)
        if not metrics:
            return None
        
        return {
            'component_name': component_name,
            'health_status': metrics.health_status,
            'success_rate': 1.0 - metrics.error_rate,
            'avg_latency_ms': metrics.avg_latency_ms,
            'total_operations': metrics.total_operations,
            'error_count': metrics.failed_operations,
            'last_operation_time': metrics.last_operation_time.isoformat() if metrics.last_operation_time else None,
            'last_error': metrics.last_error
        }

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an active alert"""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id]['status'] = 'acknowledged'
            self.logger.info(f"Alert acknowledged: {alert_id}")
            return True
        return False

    def clear_alert(self, alert_id: str) -> bool:
        """Clear an active alert"""
        if alert_id in self.active_alerts:
            alert = self.active_alerts.pop(alert_id)
            alert['status'] = 'cleared'
            alert['cleared_at'] = datetime.now().isoformat()
            self.logger.info(f"Alert cleared: {alert_id}")
            return True
        return False

    def record_component_success(self, component: str, value: float = 1.0):
        """Record successful operation for a component"""
        if component not in self.component_metrics:
            self.component_metrics[component] = PipelineMetrics(component_name=component)
        
        self.component_metrics[component].update_operation(success=True, latency_ms=0.0)
        self.logger.debug(f"Component success recorded: {component}")

    def record_component_error(self, component: str, error: str):
        """Record error for a component"""
        if component not in self.component_metrics:
            self.component_metrics[component] = PipelineMetrics(component_name=component)

        self.component_metrics[component].update_operation(success=False, latency_ms=0.0, error=error)
        self.logger.warning(f"Component error recorded: {component} - {error}")

    def record_component_metrics(self, component: str, metrics: Dict[str, Any]):
        """Record custom metrics for a component"""
        if component not in self.component_metrics:
            self.component_metrics[component] = PipelineMetrics(component_name=component)

        # Store the metrics in the component's data
        if not hasattr(self.component_metrics[component], 'custom_metrics'):
            self.component_metrics[component].custom_metrics = {}

        self.component_metrics[component].custom_metrics.update(metrics)
        self.logger.debug(f"Component metrics recorded: {component} - {metrics}")


# Global pipeline monitor instance
_pipeline_monitor: Optional[PipelineMonitor] = None

def get_pipeline_monitor() -> PipelineMonitor:
    """Get the global pipeline monitor instance"""
    global _pipeline_monitor
    if _pipeline_monitor is None:
        _pipeline_monitor = PipelineMonitor()
    return _pipeline_monitor

def initialize_pipeline_monitor(config: Optional[Dict] = None) -> PipelineMonitor:
    """Initialize the global pipeline monitor"""
    global _pipeline_monitor
    _pipeline_monitor = PipelineMonitor(config)
    return _pipeline_monitor