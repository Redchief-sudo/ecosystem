"""Utility functions for handling and validating trading opportunities."""
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

class OpportunityValidator:
    """Validates and normalizes trading opportunity data."""
    
    @staticmethod
    def validate_opportunity(
        opportunity: Dict[str, Any], 
        required_fields: list = None,
        defaults: Dict[str, Any] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate and normalize opportunity data.
        
        Args:
            opportunity: Raw opportunity data
            required_fields: List of required field names
            defaults: Default values for optional fields
            
        Returns:
            Tuple of (is_valid, normalized_data)
        """
        if not isinstance(opportunity, dict):
            logger.warning("Opportunity must be a dictionary")
            return False, {}
            
        required_fields = required_fields or []
        defaults = defaults or {}
        normalized = {}
        
        # Check required fields
        for field in required_fields:
            if field not in opportunity:
                logger.warning(f"Missing required field: {field}")
                return False, {}
                
        # Apply defaults and normalize
        for key, value in {**defaults, **opportunity}.items():
            if value is None and key in required_fields:
                logger.warning(f"Required field {key} is None")
                return False, {}
                
            # Normalize numeric fields
            if isinstance(value, (int, float)):
                normalized[key] = float(value)
            else:
                normalized[key] = value
                
        return True, normalized
        
    @staticmethod
    def get_required_fields(strategy_name: str) -> list:
        """Get required fields for a specific strategy."""
        requirements = {
            'basic': ['price', 'liquidity', 'volume'],
            'aggressive': ['price', 'volume'],
            'safe': ['price', 'volume', 'liquidity'],
            'breakout': ['price', 'volume', 'strength'],
            'mean_reversion': ['price', 'volume', 'zscore'],
            'momentum': ['price', 'volume', 'liquidity', 'price_change'],
            'ai_fusion': ['price', 'ai_models'],
            'risk_caps': ['price', 'volume', 'liquidity', 'volatility'],
            'flash_loan_arbitrage': ['price', 'profit', 'gas_cost', 'min_profit']
        }
        return requirements.get(strategy_name.lower(), [])
        
    @staticmethod
    def get_default_values(strategy_name: str) -> dict:
        """Get default values for a strategy's optional fields."""
        defaults = {
            'volume': 0.0,
            'volume_24h': 0.0,
            'liquidity': 0.0,
            'volatility': 0.0,
            'price_change': 0.0,
            'strength': 0.0,
            'zscore': 0.0,
            'ai_models': [],
            'profit': 0.0,
            'gas_cost': 0.0,
            'min_profit': 0.0
        }
        return defaults

def validate_strategy_opportunity(
    strategy_name: str, 
    opportunity: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any]]:
    """
    Validate and normalize opportunity data for a specific strategy.
    
    Args:
        strategy_name: Name of the strategy (e.g., 'basic', 'aggressive')
        opportunity: Raw opportunity data
        
    Returns:
        Tuple of (is_valid, normalized_data)
    """
    validator = OpportunityValidator()
    required_fields = validator.get_required_fields(strategy_name)
    defaults = validator.get_default_values(strategy_name)
    
    return validator.validate_opportunity(opportunity, required_fields, defaults)
