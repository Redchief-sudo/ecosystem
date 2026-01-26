#!/usr/bin/env python3
"""
Weight Monitoring Dashboard
=======================
Real-time monitoring of strategy weights and scoring biases.
"""

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

class WeightMonitoringDashboard:
    """Monitor and analyze weight distributions for bias detection."""
    
    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.weight_history = deque(maxlen=history_size)
        self.performance_history = defaultdict(list)
        self.bias_metrics = {}
        self.alerts = []
        
    def record_weights(self, timestamp: datetime, weights: Dict[str, float], 
                     regime: str, performance: Dict[str, float]):
        """Record current weights and performance metrics."""
        
        record = {
            'timestamp': timestamp.isoformat(),
            'weights': weights.copy(),
            'regime': regime,
            'performance': performance.copy(),
            'total_weight': sum(weights.values()),
            'weight_distribution': {k: v for k, v in sorted(weights.items(), key=lambda x: x[1], reverse=True)}
        }
        
        self.weight_history.append(record)
        
        # Update performance history
        for strategy, perf in performance.items():
            self.performance_history[strategy].append({
                'timestamp': timestamp,
                'performance': perf
            })
            # Keep only last 100 records per strategy
            if len(self.performance_history[strategy]) > 100:
                self.performance_history[strategy] = self.performance_history[strategy][-100:]
        
        # Analyze for biases
        self._analyze_biases()
        
        logger.info(f"📊 Recorded weights: {record['weight_distribution']}")
    
    def _analyze_biases(self):
        """Analyze weight distributions for potential biases."""
        if len(self.weight_history) < 10:
            return
        
        recent_records = list(self.weight_history)[-100:]  # Last 100 records
        
        # 1. Weight concentration analysis
        self._analyze_weight_concentration(recent_records)
        
        # 2. Regime bias analysis
        self._analyze_regime_bias(recent_records)
        
        # 3. Performance-weight correlation analysis
        self._analyze_performance_correlation(recent_records)
        
        # 4. Time-series analysis for trends
        self._analyze_weight_trends(recent_records)
    
    def _analyze_weight_concentration(self, records: List[Dict]):
        """Analyze if weights are too concentrated."""
        if not records:
            return
        
        latest = records[-1]
        weights = latest['weights']
        
        # Calculate Herfindahl-Hirschman Index (HHI)
        sorted_weights = sorted(weights.values(), reverse=True)
        n = len(sorted_weights)
        
        if n == 0:
            return
        
        hhi = sum((w / sum(sorted_weights)) ** 2 for w in sorted_weights)
        max_hhi = 1.0  # Maximum concentration
        concentration_ratio = hhi / max_hhi
        
        # Alert if concentration is too high
        if concentration_ratio > 0.5:  # 50% concentration threshold
            self._add_alert("HIGH_CONCENTRATION", 
                           f"Weight concentration too high: {concentration_ratio:.3f}",
                           latest['timestamp'])
        
        self.bias_metrics['weight_concentration'] = {
            'hhi': hhi,
            'concentration_ratio': concentration_ratio,
            'max_weight': max(sorted_weights),
            'min_weight': min(sorted_weights)
        }
    
    def _analyze_regime_bias(self, records: List[Dict]):
        """Analyze if certain regimes are favored."""
        regime_weights = defaultdict(list)
        
        for record in records:
            regime = record['regime']
            weights = record['weights']
            for metric, weight in weights.items():
                regime_weights[regime].append(weight)
        
        # Calculate average weights per regime
        regime_averages = {}
        for regime, weight_list in regime_weights.items():
            if weight_list:
                regime_averages[regime] = np.mean(weight_list)
        
        # Check for significant differences
        if len(regime_averages) > 1:
            avg_weights = list(regime_averages.values())
            max_avg = max(avg_weights)
            min_avg = min(avg_weights)
            
            if max_avg / min_avg > 2.0:  # 2x difference threshold
                favored_regime = max(regime_averages, key=regime_averages.get)
                penalized_regime = min(regime_averages, key=regime_averages.get)
                
                self._add_alert("REGIME_BIAS", 
                               f"Regime bias detected: {favored_regime} ({max_avg:.3f}) vs {penalized_regime} ({min_avg:.3f})",
                               records[-1]['timestamp'])
        
        self.bias_metrics['regime_bias'] = regime_averages
    
    def _analyze_performance_correlation(self, records: List[Dict]):
        """Analyze correlation between weights and performance."""
        if len(records) < 20:
            return
        
        # Extract weights and performance data
        df_data = []
        for record in records[-100:]:
            weights = record['weights']
            performance = record.get('performance', {})
            
            # Calculate average performance across strategies
            avg_performance = np.mean(list(performance.values())) if performance else 0.5
            
            for metric, weight in weights.items():
                perf = performance.get(metric, avg_performance)
                df_data.append({
                    'metric': metric,
                    'weight': weight,
                    'performance': perf
                })
        
        if not df_data:
            return
        
        df = pd.DataFrame(df_data)
        
        # Calculate correlation between weights and performance
        correlation = df['weight'].corr(df['performance'])
        
        # Negative correlation means higher weights with lower performance (bad)
        if correlation < -0.3:
            self._add_alert("NEGATIVE_CORRELATION", 
                           f"Weight-performance correlation: {correlation:.3f} (weights oppose performance)",
                           records[-1]['timestamp'])
        
        self.bias_metrics['performance_correlation'] = {
            'correlation': correlation,
            'sample_size': len(df_data)
        }
    
    def _analyze_weight_trends(self, records: List[Dict]):
        """Analyze weight trends over time."""
        if len(records) < 50:
            return
        
        # Extract time series data
        timestamps = [datetime.fromisoformat(r['timestamp']) for r in records[-200:]]
        
        # Analyze each metric's weight trend
        metric_trends = {}
        for metric in records[-1]['weights'].keys():
            weights = [r['weights'].get(metric, 0) for r in records[-200:]]
            
            if len(weights) > 10:
                # Calculate trend slope (linear regression)
                x = np.arange(len(weights))
                slope, intercept = np.polyfit(x, weights, 1)
                
                # Determine trend direction
                if abs(slope) > 0.001:  # Significant trend
                    trend = "increasing" if slope > 0 else "decreasing"
                    metric_trends[metric] = {
                        'slope': slope,
                        'trend': trend,
                        'volatility': np.std(weights[-50:])  # Recent volatility
                    }
        
        self.bias_metrics['weight_trends'] = metric_trends
    
    def _add_alert(self, alert_type: str, message: str, timestamp: str):
        """Add a bias alert."""
        alert = {
            'timestamp': timestamp,
            'type': alert_type,
            'message': message
        }
        
        self.alerts.append(alert)
        
        # Keep only last 100 alerts
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        logger.warning(f"🚨 BIAS ALERT [{alert_type}]: {message}")
    
    def get_bias_summary(self) -> Dict[str, Any]:
        """Get comprehensive bias analysis summary."""
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_records': len(self.weight_history),
            'recent_alerts': self.alerts[-10:],  # Last 10 alerts
            'bias_metrics': self.bias_metrics,
            'performance_summary': self._get_performance_summary(),
            'recommendations': self._generate_recommendations()
        }
    
    def _get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary by strategy."""
        summary = {}
        for strategy, performances in self.performance_history.items():
            if performances:
                recent_perfs = performances[-20:]  # Last 20 records
                summary[strategy] = {
                    'avg_performance': np.mean(recent_perfs),
                    'volatility': np.std(recent_perfs),
                    'trend': 'improving' if len(recent_perfs) > 1 and recent_perfs[-1] > recent_perfs[0] else 'stable'
                }
        
        return summary
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on bias analysis."""
        recommendations = []
        
        # Weight concentration recommendations
        if 'weight_concentration' in self.bias_metrics:
            conc = self.bias_metrics['weight_concentration']
            if conc['concentration_ratio'] > 0.5:
                recommendations.append(
                    "Consider rebalancing weights to reduce concentration (HHI > 0.5)"
                )
        
        # Performance correlation recommendations
        if 'performance_correlation' in self.bias_metrics:
            corr = self.bias_metrics['performance_correlation']
            if corr < -0.3:
                recommendations.append(
                    "Inverse correlation detected - consider inverting weight logic"
                )
        
        # Regime bias recommendations
        if 'regime_bias' in self.bias_metrics:
            recommendations.append(
                "Monitor regime-specific performance and adjust weights accordingly"
            )
        
        return recommendations
    
    def export_report(self, filepath: str):
        """Export bias analysis report to file."""
        report = self.get_bias_summary()
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"📄 Bias report exported to {filepath}")

# Singleton instance
dashboard = WeightMonitoringDashboard()

async def monitor_weights(weights: Dict[str, float], regime: str, performance: Dict[str, float]):
    """Convenience function to record weights."""
    dashboard.record_weights(
        timestamp=datetime.now(timezone.utc),
        weights=weights,
        regime=regime,
        performance=performance
    )

if __name__ == "__main__":
    # Test the dashboard
    test_weights = {
        'price_momentum': 0.3,
        'volume_liquidity': 0.25,
        'market_cap': 0.2,
        'volatility': 0.15,
        'social_sentiment': 0.1
    }
    
    test_performance = {
        'base_ai': 0.8,
        'technical': 0.6,
        'volume': 0.7,
        'risk': 0.45
    }
    
    asyncio.run(monitor_weights(test_weights, "bull", test_performance))
    
    print("Bias analysis complete!")
    print(json.dumps(dashboard.get_bias_summary(), indent=2))
