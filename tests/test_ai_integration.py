import asyncio
import logging
from ai.elite_async_ai_controller import EliteAsyncAIController as AIController

logging.basicConfig(level=logging.INFO)

async def test_ai_controller():
    """Test the AI controller integration."""
    config = {'ai': {'primary_method': 'ensemble'}}
    
    # Initialize the AI controller
    ai_controller = AIController(config=config)
    
    # Test with sample token data
    token_data = {
        'address': '0x1234567890123456789012345678901234567890',
        'symbol': 'TEST',
        'price': 100.0,
        'volume': 1000000
    }
    
    # Make a decision
    decision = await ai_controller.make_decision(token_data)
    
    print("AI Controller Decision:")
    for field, value in decision.__dict__.items():
        print(f"  {field}: {value}")
    
    # Test readiness
    print(f"AI Controller Ready: {ai_controller.is_ready}")

if __name__ == "__main__":
    asyncio.run(test_ai_controller())
