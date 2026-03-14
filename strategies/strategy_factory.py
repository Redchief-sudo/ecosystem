from __future__ import annotations
import logging
from typing import Dict, List, Any

from .base_strategy import BaseStrategy
from .registry import StrategyRegistry

logger = logging.getLogger(__name__)


def create_strategies_from_config(config: Dict[str, Any], registry: StrategyRegistry) -> List[BaseStrategy]:
    """
    Creates enabled strategies from configuration.

    Config schema:

    strategies:
      enabled:
        - momentum
        - mean_reversion

      configs:
        momentum:
          enabled: true
          lookback: 60
        mean_reversion:
          enabled: true
          lookback: 120
    """
    strategies_enabled = config.get("strategies", {}).get("enabled", [])
    strategies_configs = config.get("strategies", {}).get("configs", {})

    strategies: List[BaseStrategy] = []

    for key in strategies_enabled:
        strategy_cls = registry.get(key)

        if strategy_cls is None:
            logger.error(f"Strategy '{key}' not found in registry")
            continue

        strategy_config = strategies_configs.get(key)
        if not strategy_config:
            logger.error(f"No configuration found for strategy '{key}'")
            continue

        try:
            instance = strategy_cls(strategy_config, config)
            strategies.append(instance)
            logger.info(f"Loaded strategy: {key}")
        except Exception as e:
            logger.exception(f"Failed to create strategy '{key}': {e}")

    return strategies

