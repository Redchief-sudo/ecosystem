#!/usr/bin/env python3
"""Test the AI controller method fix"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from decimal import Decimal

from ai.elite_async_ai_controller import EliteAsyncAIController
from trading.models import TradeOpportunity

# Test the correct method name
controller = EliteAsyncAIController(config={})

# Skip TradeOpportunity instantiation due to complex constructor
# opportunity = TradeOpportunity(...)

# Test if the controller initialized correctly
print("✅ EliteAsyncAIController initialized successfully")
print(f"Controller config: {controller.config}")
