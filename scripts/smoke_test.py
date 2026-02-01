#!/usr/bin/env python3
"""
Smoke test for ecosystem - verifies core components load correctly
"""
import sys
import asyncio

def test_imports():
    """Verify all critical modules can be imported."""
    print("🔍 Testing critical imports...")
    
    try:
        from ai.elite_async_ai_controller import EliteAsyncAIController
        from core.task_manager import task_manager
        from networks.universal_network_manager import UniversalNetworkManager
        from trading.execution.trade_executor import HybridTradeExecutor
        from utils.onchain_client import OnchainClient
        from config import load_config
        print("   ✅ All critical imports successful")
        return True
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        return False

def test_config():
    """Verify config loads correctly."""
    print("🔍 Testing config loading...")
    
    try:
        from config import load_config
        config = load_config()
        
        assert 'networks' in config, "Missing networks section"
        assert 'strategies' in config, "Missing strategies section"
        assert 'trading' in config, "Missing trading section"
        
        print(f"   ✅ Config loaded: {len(config.get('networks', {}))} networks, {len(config.get('strategies', {}))} strategies")
        return True
    except Exception as e:
        print(f"   ❌ Config test failed: {e}")
        return False

async def test_async_components():
    """Verify async components initialize."""
    print("🔍 Testing async component initialization...")
    
    try:
        from ai.elite_async_ai_controller import EliteAsyncAIController
        
        controller = EliteAsyncAIController(config={'health_check_interval': 0.01})
        await controller.async_initialize()
        
        assert controller._started, "Controller not started"
        
        await controller.shutdown()
        
        print("   ✅ Async components initialize correctly")
        return True
    except Exception as e:
        print(f"   ❌ Async test failed: {e}")
        return False

def main():
    """Run all smoke tests."""
    print("🚀 Running Ecosystem Smoke Tests")
    print("=" * 50)
    print()
    
    results = []
    
    # Synchronous tests
    results.append(test_imports())
    results.append(test_config())
    
    # Async tests
    results.append(asyncio.run(test_async_components()))
    
    print()
    print("=" * 50)
    
    if all(results):
        print("✅ All smoke tests passed!")
        return 0
    else:
        print("❌ Some smoke tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
