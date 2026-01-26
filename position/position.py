"""
Position Manager
----------------
Production-grade position management and risk assessment system.
Handles active position monitoring, risk evaluation, and position-level decisions.

Version: 1.0.0
Author: Trading System
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging
import time
from decimal import Decimal

from .policy import PositionPolicy, PositionPolicyType, get_default_policy
from .verdict import PositionVerdict, PositionAssessment, PositionRiskLevel

logger = logging.getLogger(__name__)


@dataclass
class PositionMetrics:
    """Position performance and risk metrics."""
    pnl_percent: float
    unrealized_pnl_usd: float
    position_size_usd: float
    duration_hours: float
    volatility: float
    drawdown_percent: float
    risk_score: float
    last_updated: float


class PositionManager:
    """
    Position Manager - handles active position monitoring and risk assessment.

    This component evaluates active positions against risk policies and provides
    recommendations for position management, risk reduction, or closure.
    """

    def __init__(self, config: Dict[str, Any], policy: Optional[PositionPolicy] = None):
        """
        Initialize the Position Manager.

        Args:
            config: Position management configuration
            policy: Position policy to use (optional, uses default if not provided)
        """
        self.config = config
        self.policy = policy or get_default_policy()

        # Position tracking
        self.active_positions: Dict[str, PositionMetrics] = {}
        self.position_history: Dict[str, List[PositionMetrics]] = {}

        logger.info("Position Manager initialized")
        logger.info(f"Using policy: {self.policy.name}")
        logger.info(f"Policy thresholds: dd={self.policy.max_drawdown_percent} crit={self.policy.critical_risk_threshold} high={self.policy.high_risk_threshold}")

    def assess_position(self, position_id: str, position_data: Dict[str, Any]) -> PositionAssessment:
        """
        Assess a position against risk policy.

        Args:
            position_id: Unique position identifier
            position_data: Current position data

        Returns:
            PositionAssessment with verdict and recommendations
        """
        try:
            # Extract position metrics
            metrics = self._extract_position_metrics(position_data)

            # Update tracking
            self.active_positions[position_id] = metrics
            if position_id not in self.position_history:
                self.position_history[position_id] = []
            self.position_history[position_id].append(metrics)

            # Assess against policy
            assessment = self._evaluate_position_risks(position_id, metrics)

            # Log assessment
            self._log_position_assessment(position_id, assessment)

            return assessment

        except Exception as e:
            logger.error(f"Error assessing position {position_id}: {e}", exc_info=True)
            return PositionAssessment(
                verdict=PositionVerdict.UNKNOWN,
                reason=f"Assessment error: {str(e)}",
                risk_level=PositionRiskLevel.CRITICAL,
                confidence=0.0
            )

    def _extract_position_metrics(self, position_data: Dict[str, Any]) -> PositionMetrics:
        """Extract position metrics from position data."""
        drawdown = float(position_data.get('drawdown_percent', 0.0))
        if drawdown > 1.0:
            drawdown = drawdown / 100.0
        return PositionMetrics(
            pnl_percent=float(position_data.get('pnl_percent', 0.0)),
            unrealized_pnl_usd=float(position_data.get('unrealized_pnl_usd', 0.0)),
            position_size_usd=float(position_data.get('position_size_usd', 0.0)),
            duration_hours=float(position_data.get('duration_hours', 0.0)),
            volatility=float(position_data.get('volatility', 0.1)),
            drawdown_percent=drawdown,
            risk_score=float(position_data.get('risk_score', 0.5)),
            last_updated=time.time()
        )

    def _evaluate_position_risks(self, position_id: str, metrics: PositionMetrics) -> PositionAssessment:
        """Evaluate position against risk policy and thresholds."""

        # Check critical conditions first
        if self._is_critical_risk(metrics):
            # Terminal loss condition
            if metrics.pnl_percent <= -70.0:
                return PositionAssessment(
                    verdict=PositionVerdict.CLOSE_POSITION,
                    reason="Maximum loss exceeded",
                    risk_level=PositionRiskLevel.CRITICAL,
                    confidence=0.99,
                    recommendations=self._get_critical_recommendations(metrics)
                )
            return PositionAssessment(
                verdict=PositionVerdict.REDUCE_RISK,
                reason="Critical risk conditions detected",
                risk_level=PositionRiskLevel.CRITICAL,
                confidence=0.95,
                recommendations=self._get_critical_recommendations(metrics)
            )

        # Check high risk conditions
        if self._is_high_risk(metrics):
            return PositionAssessment(
                verdict=PositionVerdict.MONITOR_CLOSELY,
                reason="High risk conditions detected",
                risk_level=PositionRiskLevel.HIGH,
                confidence=0.85,
                recommendations=self._get_high_risk_recommendations(metrics)
            )

        # Check moderate risk
        if self._is_moderate_risk(metrics):
            return PositionAssessment(
                verdict=PositionVerdict.MONITOR,
                reason="Moderate risk conditions",
                risk_level=PositionRiskLevel.MODERATE,
                confidence=0.7,
                recommendations=self._get_moderate_risk_recommendations(metrics)
            )

        # Low risk - position healthy
        return PositionAssessment(
            verdict=PositionVerdict.HEALTHY,
            reason="Position within acceptable risk parameters",
            risk_level=PositionRiskLevel.LOW,
            confidence=0.9,
            recommendations=[]
        )

    def _is_critical_risk(self, metrics: PositionMetrics) -> bool:
        """Check if position has critical risk."""
        return (
            metrics.drawdown_percent >= self.policy.max_drawdown_percent or
            metrics.drawdown_percent >= self.policy.auto_close_threshold or
            metrics.risk_score >= self.policy.critical_risk_threshold or
            metrics.duration_hours >= self.policy.max_position_duration_hours or
            metrics.pnl_percent <= -50.0  # 50% loss
        )

    def _is_high_risk(self, metrics: PositionMetrics) -> bool:
        """Check if position has high risk."""
        return (
            metrics.drawdown_percent >= self.policy.auto_reduce_threshold or
            metrics.risk_score >= self.policy.high_risk_threshold or
            metrics.pnl_percent <= -25.0  # 25% loss
        )

    def _is_moderate_risk(self, metrics: PositionMetrics) -> bool:
        """Check if position has moderate risk."""
        return (
            metrics.drawdown_percent >= self.policy.max_drawdown_percent * 0.5 or
            metrics.volatility >= 0.5 or
            metrics.duration_hours >= self.policy.max_position_duration_hours * 0.7
        )

    def _get_critical_recommendations(self, metrics: PositionMetrics) -> List[str]:
        """Get recommendations for critical risk positions."""
        recommendations = []

        if metrics.drawdown_percent >= self.policy.max_drawdown_percent:
            recommendations.append("Immediate position reduction due to excessive drawdown")

        if metrics.pnl_percent <= -50.0:
            recommendations.append("Consider position closure due to significant losses")

        if metrics.duration_hours >= self.policy.max_position_duration_hours:
            recommendations.append("Position held too long - reassess strategy")

        recommendations.append("Immediate risk management intervention required")
        return recommendations

    def _get_high_risk_recommendations(self, metrics: PositionMetrics) -> List[str]:
        """Get recommendations for high risk positions."""
        recommendations = []

        if metrics.drawdown_percent >= self.policy.max_drawdown_percent * 0.8:
            recommendations.append("Reduce position size to limit further drawdown")

        if metrics.pnl_percent <= -25.0:
            recommendations.append("Consider partial position exit")

        recommendations.append("Close monitoring required")
        return recommendations

    def _get_moderate_risk_recommendations(self, metrics: PositionMetrics) -> List[str]:
        """Get recommendations for moderate risk positions."""
        recommendations = []

        if metrics.volatility >= 0.5:
            recommendations.append("Monitor volatility closely")

        if metrics.duration_hours >= self.policy.max_position_duration_hours * 0.7:
            recommendations.append("Consider exit timing")

        recommendations.append("Regular monitoring advised")
        return recommendations

    def _log_position_assessment(self, position_id: str, assessment: PositionAssessment):
        """Log position assessment for audit purposes."""
        if assessment.verdict == PositionVerdict.HEALTHY:
            logger.info(f"Position {position_id}: {assessment.reason}")
        elif assessment.verdict == PositionVerdict.MONITOR:
            logger.info(f"Position {position_id}: {assessment.reason}")
        elif assessment.verdict == PositionVerdict.MONITOR_CLOSELY:
            logger.warning(f"Position {position_id}: {assessment.reason}")
        elif assessment.verdict == PositionVerdict.REDUCE_RISK:
            logger.error(f"Position {position_id}: {assessment.reason}")

    def get_position_summary(self, position_id: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive summary for a position."""
        if position_id not in self.active_positions:
            return None

        metrics = self.active_positions[position_id]
        history = self.position_history.get(position_id, [])

        return {
            'position_id': position_id,
            'current_metrics': {
                'pnl_percent': metrics.pnl_percent,
                'unrealized_pnl_usd': metrics.unrealized_pnl_usd,
                'position_size_usd': metrics.position_size_usd,
                'duration_hours': metrics.duration_hours,
                'volatility': metrics.volatility,
                'drawdown_percent': metrics.drawdown_percent,
                'risk_score': metrics.risk_score,
            },
            'risk_assessment': self._evaluate_position_risks(position_id, metrics),
            'history_length': len(history),
            'policy_name': self.policy.name,
            'last_updated': metrics.last_updated
        }

    def assess_new_opportunity(self, opportunity, entry_assessment) -> PositionAssessment:
        """
        Assess a new opportunity to determine if we can open a position.
        
        This is different from assess_position() which evaluates existing positions.
        This method checks if we can open a new position and suggests a size.
        
        Args:
            opportunity: TradeOpportunity object
            entry_assessment: EntryAssessment from entry manager
            
        Returns:
            PositionAssessment with suggested_size in metadata if approved
        """
        try:
            # Check if we're at max positions limit
            # Read from config, with fallback to risk manager limits or default
            max_positions = self.config.get("max_positions")
            if max_positions is None:
                # Try to get from risk limits if available
                risk_config = self.config.get("risk_management", {})
                max_positions = risk_config.get("max_concurrent_positions", 10)
            
            if len(self.active_positions) >= max_positions:
                return PositionAssessment(
                    verdict=PositionVerdict.MONITOR,
                    reason=f"At maximum position limit ({max_positions})",
                    risk_level=PositionRiskLevel.MODERATE,
                    confidence=0.5,
                    metadata={'suggested_size': Decimal('0')}
                )

            # FIX: Calculate suggested position size more reasonably
            # Use a fixed base amount scaled by confidence, without excessive multipliers
            base_position_size_usd = self.config.get("base_position_size", 100.0)  # $100 default base
            confidence_multiplier = entry_assessment.confidence  # 0.0-1.0

            # Position size = base * confidence * risk factor
            # This gives: $100 * 0.7 = $70 for high confidence trades
            suggested_size_usd = base_position_size_usd * confidence_multiplier

            # Cap at max position size from config
            max_size_usd = self.config.get("max_position_size", 500.0)  # $500 max
            suggested_size_usd = min(suggested_size_usd, max_size_usd)

            # Minimum position size check (enough to be profitable after gas)
            min_size_usd = self.config.get("min_position_size", 50.0)  # $50 minimum
            if suggested_size_usd < min_size_usd:
                # Still allow the trade but at minimum size
                suggested_size_usd = min_size_usd
            
            # Create position data for assessment
            position_data = {
                'position_id': opportunity.opportunity_id,
                'pnl_percent': 0.0,  # New position, no PnL yet
                'unrealized_pnl_usd': 0.0,
                'position_size_usd': suggested_size_usd,
                'duration_hours': 0.0,  # New position
                'volatility': float(opportunity.volatility) if hasattr(opportunity, 'volatility') else 0.1,
                'drawdown_percent': 0.0,  # No drawdown yet
                'risk_score': 1.0 - entry_assessment.confidence,  # Higher confidence = lower risk
            }
            
            # Assess using existing position assessment logic
            assessment = self.assess_position(opportunity.opportunity_id, position_data)
            
            # Add suggested_size to metadata
            if assessment.metadata is None:
                assessment.metadata = {}
            assessment.metadata['suggested_size'] = Decimal(str(suggested_size_usd))
            
            return assessment
            
        except Exception as e:
            logger.error(f"Error assessing new opportunity: {e}", exc_info=True)
            return PositionAssessment(
                verdict=PositionVerdict.UNKNOWN,
                reason=f"Assessment error: {str(e)}",
                risk_level=PositionRiskLevel.CRITICAL,
                confidence=0.0,
                metadata={'suggested_size': Decimal('0')}
            )

    def get_portfolio_risk_summary(self) -> Dict[str, Any]:
        """Get portfolio-wide risk summary."""
        if not self.active_positions:
            return {'total_positions': 0, 'risk_distribution': {}}

        risk_counts = {
            PositionRiskLevel.LOW: 0,
            PositionRiskLevel.MODERATE: 0,
            PositionRiskLevel.HIGH: 0,
            PositionRiskLevel.CRITICAL: 0
        }

        total_pnl = 0.0
        total_risk_score = 0.0

        for position_id, metrics in self.active_positions.items():
            assessment = self._evaluate_position_risks(position_id, metrics)
            risk_counts[assessment.risk_level] += 1
            total_pnl += metrics.pnl_percent
            total_risk_score += metrics.risk_score

        avg_pnl = total_pnl / len(self.active_positions)
        avg_risk = total_risk_score / len(self.active_positions)

        return {
            'total_positions': len(self.active_positions),
            'average_pnl_percent': avg_pnl,
            'average_risk_score': avg_risk,
            'risk_distribution': {level.value: count for level, count in risk_counts.items()},
            'critical_positions': risk_counts[PositionRiskLevel.CRITICAL],
            'high_risk_positions': risk_counts[PositionRiskLevel.HIGH],
            'policy_name': self.policy.name
        }

    def update_policy(self, new_policy: PositionPolicy):
        """Update the risk policy."""
        self.policy = new_policy
        logger.info(f"Updated position policy to: {new_policy.name}")

    def remove_position(self, position_id: str):
        """Remove a position from tracking."""
        if position_id in self.active_positions:
            del self.active_positions[position_id]
            logger.info(f"Removed position {position_id} from tracking")


# Factory function
def create_position_manager(config: Dict[str, Any], policy: Optional[PositionPolicy] = None) -> PositionManager:
    """Factory function to create PositionManager instance."""
    return PositionManager(config, policy)
