"""
Signal Types Module
===================

Shared signal data structures to avoid circular imports between
elite_strategy_manager and elite_async_ai_controller.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict

from strategies.base_strategy import SignalType


@dataclass
class NormalizedSignal:
    """
    Standardized signal schema for Elite AI Controller.
    All strategies must output signals in this format.
    """
    strategy_id: str
    signal_type: SignalType
    direction: str  # 'long', 'short', 'none'
    confidence: float  # 0.0 to 1.0
    expected_edge: float  # Expected profit/loss %
    max_risk: float  # Maximum acceptable risk %
    token_address: str
    token_symbol: str
    price: float
    position_size: float
    ttl: int  # Time to live in seconds
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
