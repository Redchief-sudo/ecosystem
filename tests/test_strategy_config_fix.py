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
        return False
    
    strategies_config = config.get('strategies', {})
    
    # Test all the strategy lookup methods
    test_cases = [
        # (strategy_class_name, strategy_name, STRATEGY_NAME)
        ("EliteMomentumStrategy", "momentum", "momentum_strategy"),
        ("MeanReversionStrategy", "mean_reversion", "mean_reversion_strategy"),
        ("EliteBreakoutStrategy", "breakout", "elite_breakout_strategy"),
        ("VolatilityBreakoutStrategy", "volatility_breakout", "volatility_breakout_strategy"),
        ("EliteAggressiveStrategy", "aggressive", "aggressive_strategy"),
        ("RiskCapsStrategy", "risk_caps", "risk_caps_strategy"),
        ("ProfessionalEliteStrategy", "professional_elite", "safe_strategy"),
        ("SmartMoneyUltraStrategy", "smart_money", "smart_money_ultra_elite"),
    ]
    
    all_found = True
    for class_name, name1, name2 in test_cases:
        # Test class name lookup
        class_found = class_name in strategies_config
        status1 = "✅" if class_found else "❌"
        
        # Test name lookup
        name1_found = name1 in strategies_config
        status2 = "✅" if name1_found else "❌"
        
        # Test STRATEGY_NAME lookup
        name2_found = name2 in strategies_config
        status3 = "✅" if name2_found else "❌"
        
        print(f"   {status1} {class_name}")
        print(f"   {status2} {name1}")
        print(f"   {status3} {name2}")
        
        if not (class_found or name1_found or name2_found):
            all_found = False
            print(f"      ❌ {class_name} - Missing config")
        else:
            print(f"      ✅ {class_name} - Config found")
    
    return all_found

def test_strategy_instantiation():
    """Test that strategies can be instantiated with their configs."""
    print(f"\n🧪 Testing Strategy Instantiation...\n")
    
    try:
        from strategies.features.momentum import EliteMomentumStrategy
        from strategies.features.mean_reversion import MeanReversionStrategy
        
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        strategies_config = config.get('strategies', {})
        
        # Test EliteMomentumStrategy
        try:
            momentum_strategy = EliteMomentumStrategy(config=strategies_config)
            print(f"   ✅ EliteMomentumStrategy: Instantiated successfully")
        except Exception as e:
            print(f"   ❌ EliteMomentumStrategy: {e}")
            return False
        
        # Test MeanReversionStrategy
        try:
            mean_reversion_strategy = MeanReversionStrategy(config=strategies_config)
            print(f"   ✅ MeanReversionStrategy: Instantiated successfully")
        except Exception as e:
            print(f"   ❌ MeanReversionStrategy: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy instantiation test failed: {e}")
        return False

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
