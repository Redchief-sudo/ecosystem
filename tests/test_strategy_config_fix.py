#!/usr/bin/env python3
"""
Test Strategy Configuration Fix
==========================

Verify that all strategies can now find their configurations.
"""

import sys
import yaml
from pathlib import Path

def test_strategy_config_fix():
    """Test that all strategies can find their configurations."""
    print("🧪 Testing Strategy Configuration Fix...\n")
    
    config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        assert False, f"Failed to load config: {e}"
    
    strategies_config = config.get('strategies', {})
    
    # Test the ACTUAL config keys that strategies use
    expected_strategies = [
        "elite_momentum",
        "mean_reversion",
        "elite_breakout",
        "volatility_breakout",
        "elite_aggressive",
        "risk_caps",
        "professional_elite",
        "smart_money_ultra"
    ]
    
    all_found = True
    for strategy_key in expected_strategies:
        found = strategy_key in strategies_config
        status = "✅" if found else "❌"
        print(f"   {status} {strategy_key}")
        
        if not found:
            all_found = False
            print(f"      ❌ {strategy_key} - Missing config")
        else:
            print(f"      ✅ {strategy_key} - Config found")
    
    assert all_found, f"Some strategies are missing config. Found {len([k for k in expected_strategies if k in strategies_config])}/{len(expected_strategies)}"

def test_strategy_instantiation():
    """Test that strategies can be instantiated with their configs."""
    print(f"\n🧪 Testing Strategy Instantiation...\n")
    
    try:
        from strategies.features.momentum import EliteMomentumStrategy
        from strategies.features.mean_reversion import MeanReversionStrategyV2
        
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        strategies_config = config.get('strategies', {})
        
        # Test EliteMomentumStrategy
        # Strategies expect (strategy_config, global_config) not just config dict
        try:
            strategy_config = strategies_config.get('elite_momentum', {})
            momentum_strategy = EliteMomentumStrategy(
                strategy_config=strategy_config,
                global_config=config
            )
            print(f"   ✅ EliteMomentumStrategy: Instantiated successfully")
        except Exception as e:
            print(f"   ❌ EliteMomentumStrategy: {e}")
            assert False, f"EliteMomentumStrategy instantiation failed: {e}"
        
        # Test MeanReversionStrategyV2
        try:
            strategy_config = strategies_config.get('mean_reversion', {})
            mean_reversion_strategy = MeanReversionStrategyV2(
                strategy_config=strategy_config,
                global_config=config
            )
            print(f"   ✅ MeanReversionStrategyV2: Instantiated successfully")
        except Exception as e:
            print(f"   ❌ MeanReversionStrategyV2: {e}")
            assert False, f"MeanReversionStrategyV2 instantiation failed: {e}"
        

        
    except Exception as e:
        print(f"❌ Strategy instantiation test failed: {e}")
        assert False, f"Strategy instantiation test failed: {e}"

def main():
    """Main test function."""
    print("🎯 Testing Strategy Configuration Fix")
    print("=" * 40)
    
    # Test 1: Configuration lookup
    config_ok = test_strategy_config_fix()
    
    # Test 2: Strategy instantiation
    instantiation_ok = test_strategy_instantiation()
    
    print(f"\n📊 Test Results:")
    print(f"   Configuration: {'✅ PASS' if config_ok else '❌ FAIL'}")
    print(f"   Instantiation: {'✅ PASS' if instantiation_ok else '❌ FAIL'}")
    
    all_ok = config_ok and instantiation_ok
    
    if all_ok:
        print(f"\n🎉 STRATEGY CONFIGURATION IS WORKING!")
        print(f"✅ All strategies can now find their configurations")
        print(f"✅ No more 'No configuration found' errors")
        print(f"✅ Restart the application to pick up the new configuration")
    else:
        print(f"\n❌ Strategy configuration still has issues")
    
    return all_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
