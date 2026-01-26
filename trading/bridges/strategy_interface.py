#!/usr/bin/env python3
"""
Example strategy interface for the new trading loop architecture.
"""
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class BaseStrategy(ABC):
    """Base interface for trading strategies"""
    
    def __init__(self, name: str, poll_interval: float = 1.0):
        self.name = name
        self.poll_interval = poll_interval
    
    @abstractmethod
    async def scan_market(self) -> Optional[Dict[str, Any]]:
        """Scan market for opportunities"""
        pass
    
    @abstractmethod
    async def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate market data and generate trading signals"""
        pass

class ExampleMomentumStrategy(BaseStrategy):
    """Example momentum strategy for testing"""
    
    def __init__(self):
        super().__init__("ExampleMomentumStrategy", poll_interval=2.0)
        self.counter = 0
    
    async def scan_market(self) -> Optional[Dict[str, Any]]:
        """Mock market scanning"""
        await asyncio.sleep(0.1)  # Simulate API call
        
        # Return mock market data
        return {
            "symbol": "ETH/USDT",
            "price": 2000.0 + (self.counter % 100),
            "volume": 1000000,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    async def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mock signal evaluation"""
        await asyncio.sleep(0.05)  # Simulate computation
        
        self.counter += 1
        
        # Generate a signal every 10 iterations
        if self.counter % 10 == 0:
            return {
                "symbol": market_data["symbol"],
                "action": "buy",
                "price": market_data["price"],
                "size": 0.1,  # 0.1 ETH
                "confidence": 0.8,
                "reasoning": "Momentum detected - price increasing"
            }
        
        return None

class ExampleArbitrageStrategy(BaseStrategy):
    """Example arbitrage strategy for testing"""
    
    def __init__(self):
        super().__init__("ExampleArbitrageStrategy", poll_interval=3.0)
        self.counter = 0
    
    async def scan_market(self) -> Optional[Dict[str, Any]]:
        """Mock market scanning for arbitrage"""
        await asyncio.sleep(0.2)  # Simulate API calls
        
        return {
            "exchange1": {"symbol": "BTC/USDT", "price": 50000.0},
            "exchange2": {"symbol": "BTC/USDT", "price": 50100.0},
            "spread": 100.0,
            "timestamp": asyncio.get_event_loop().time()
        }
    
    async def evaluate(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Mock arbitrage evaluation"""
        await asyncio.sleep(0.1)  # Simulate computation
        
        self.counter += 1
        
        # Generate arbitrage signal if spread > 50
        if market_data["spread"] > 50 and self.counter % 8 == 0:
            return {
                "type": "arbitrage",
                "buy_exchange": "exchange1",
                "sell_exchange": "exchange2",
                "symbol": "BTC/USDT",
                "size": 0.05,  # 0.05 BTC
                "expected_profit": market_data["spread"] * 0.05,
                "confidence": 0.9,
                "reasoning": f"Arbitrage opportunity: ${market_data['spread']} spread"
            }
        
        return None

# Example usage
async def demo_strategies():
    """Demonstrate strategy interface"""
    
    strategies = [
        ExampleMomentumStrategy(),
        ExampleArbitrageStrategy()
    ]
    
    print("🧪 Testing Strategy Interface...")
    
    for strategy in strategies:
        print(f"\n📊 Testing {strategy.name}:")
        
        # Test market scanning
        market_data = await strategy.scan_market()
        print(f"  Market data: {market_data}")
        
        # Test signal evaluation
        signal = await strategy.evaluate(market_data)
        print(f"  Signal: {signal}")
    
    print(f"\n✅ Strategy interface working correctly!")

if __name__ == "__main__":
    asyncio.run(demo_strategies())
