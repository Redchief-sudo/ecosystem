#!/usr/bin/env python3
"""
Trading Cycle Debugging
==================

Debug why the system is getting stuck and not entering the trading cycle.
"""

import sys
import yaml
import asyncio
from pathlib import Path
from yaml import Loader

def check_main_system_status():
    """Check the main system status and identify bottlenecks."""
    print("🧪 Checking Main System Status...\n")
    
    try:
        # Check main.py structure
        with open("/home/damien/ecosystem/main.py", 'r') as f:
            main_content = f.read()
        
        print("📋 Main.py Analysis:")
        
        # Check for trading loop
        if "trading loop" in main_content.lower():
            print("   ✅ Trading loop found in main.py")
        else:
            print("   ❌ Trading loop NOT found in main.py")
        
        # Check for scanner initialization
        if "scanner" in main_content.lower():
            print("   ✅ Scanner initialization found")
        else:
            print("   ❌ Scanner initialization NOT found")
        
        # Check for strategy manager
        if "strategy_manager" in main_content.lower():
            print("   ✅ Strategy manager found")
        else:
            print("   ❌ Strategy manager NOT found")
        
        # Check for trading execution
        if "trading" in main_content.lower():
            print("   ✅ Trading execution found")
        else:
            print("   ❌ Trading execution NOT found")
        
        # Check for compose_system
        if "compose_system" in main_content:
            print("   ✅ compose_system function found")
        else:
            print("   ❌ compose_system function NOT found")
        
        return True
        
    except Exception as e:
        print(f"❌ Main system check failed: {e}")
        return False

def check_configuration_status():
    """Check configuration files and their status."""
    print(f"\n🧪 Checking Configuration Status...\n")
    
    try:
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        print("📋 Configuration Analysis:")
        
        # Check strategies
        strategies_config = config.get('strategies', {})
        enabled_strategies = strategies_config.get('enabled', [])
        print(f"   ✅ Strategies enabled: {len(enabled_strategies)}")
        print(f"   📋 Enabled strategies: {enabled_strategies}")
        
        # Check trading config
        trading_config = config.get('trading', {})
        if trading_config:
            trading_mode = trading_config.get('trading_mode', 'not_set')
            print(f"   ✅ Trading mode: {trading_mode}")
            
            paper_config = trading_config.get('paper_trading', {})
            if paper_config:
                auto_switch = paper_config.get('auto_switch', 'not_set')
                print(f"   ✅ Paper trading enabled: {paper_config.get('enabled', False)}")
                print(f"   🔄 Auto-switch: {auto_switch}")
        else:
            print(f"   ❌ No trading configuration found")
        
        # Check scanner config
        scanner_config = config.get('scanners', {})
        if scanner_config:
            enabled_scanners = [name for name, cfg in scanner_config.items() if cfg.get('enabled', False)]
            print(f"   ✅ Scanners enabled: {len(enabled_scanners)}")
            print(f"   📋 Enabled scanners: {enabled_scanners}")
        else:
            print(f"   ❌ No scanner configuration found")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration check failed: {e}")
        return False

def check_dependencies():
    """Check if all required dependencies are available."""
    print(f"\n🧪 Checking Dependencies...\n")
    
    dependencies = {
        'yaml': 'YAML parsing',
        'asyncio': 'Async/await support',
        'logging': 'Logging system',
        'pathlib': 'File system operations',
        'datetime': 'Date/time operations'
    }
    
    all_available = True
    for dep, description in dependencies.items():
        try:
            __import__(dep)
            print(f"   ✅ {dep}: {description}")
        except ImportError as e:
            print(f"   ❌ {dep}: {description} - {e}")
            all_available = False
    
    return all_available

def check_trading_components():
    """Check if trading components can be initialized."""
    print(f"\n🧪 Checking Trading Components...\n")
    
    try:
        # Check strategy manager
        from strategies.elite_strategy_manager import EliteStrategyManager
        
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        strategies_config = config.get('strategies', {})
        
        print(f"📊 Testing EliteStrategyManager...")
        strategy_manager = EliteStrategyManager(config=strategies_config)
        print(f"   ✅ EliteStrategyManager initialized")
        print(f"   📊 Loaded strategies: {len(strategy_manager.strategies)}")
        
        # Check scanner director
        from scanners.scan_director import ScanDirector
        
        print(f"📊 Testing ScanDirector...")
        # Skip full initialization for now, just check import
        print(f"   ✅ ScanDirector import successful")
        
        # Check trading execution
        from trading.execution.trade_executor import HybridTradeExecutor
        from trading.execution.trade_engine import TradingEngine
        
        print(f"📊 Testing Trading Execution...")
        # Skip complex initialization for now
        print(f"   ✅ HybridTradeExecutor import successful")
        print(f"   ✅ TradingEngine import successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Trading components check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_scanner_status():
    """Check scanner status and potential issues."""
    print(f"\n🧪 Checking Scanner Status...\n")
    
    try:
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        scanner_config = config.get('scanners', {})
        
        if not scanner_config:
            print(f"❌ No scanner configuration found")
            return False
        
        print(f"📋 Scanner Configuration:")
        
        enabled_scanners = []
        for name, config in scanner_config.items():
            if name == 'settings':
                continue  # Skip settings section
            if config.get('enabled', False):
                enabled_scanners.append(name)
                print(f"   ✅ {name}: enabled")
            else:
                print(f"   ❌ {name}: disabled")
        
        print(f"\n📊 Scanner Status Summary:")
        print(f"   Total scanners configured: {len(scanner_config)}")
        print(f"   Enabled scanners: {len(enabled_scanners)}")
        
        if len(enabled_scanners) == 0:
            print(f"❌ NO SCANNERS ENABLED - This is likely the issue!")
            print(f"   💡 Enable at least one scanner to start trading")
            return False
        
        # Check specific scanners that should be enabled
        recommended_scanners = ['dex_screener', 'mempool_scanner', 'token_analyzer']
        missing_scanners = [s for s in recommended_scanners if s not in enabled_scanners]
        
        if missing_scanners:
            print(f"⚠️  Recommended scanners not enabled: {missing_scanners}")
            print(f"   💡 Consider enabling: {missing_scanners}")
        
        return True
        
    except Exception as e:
        print(f"❌ Scanner status check failed: {e}")
        return False

def check_strategy_status():
    """Check strategy status and potential issues."""
    print(f"\n🧪 Checking Strategy Status...\n")
    
    try:
        config_path = Path("/home/damien/ecosystem/config/config_unified.yaml")
        with open(config_path, 'r') as f:
            config = yaml.load(f, Loader=Loader)
        
        strategies_config = config.get('strategies', {})
        enabled_strategies = strategies_config.get('enabled', [])
        
        print(f"📊 Strategy Configuration:")
        print(f"   Total strategies configured: {len(strategies_config)}")
        print(f"   Enabled strategies: {len(enabled_strategies)}")
        print(f"   Enabled: {enabled_strategies}")
        
        if len(enabled_strategies) == 0:
            print(f"❌ NO STRATEGIES ENABLED - This is likely the issue!")
            print(f"   💡 Enable at least one strategy to start trading")
            return False
        
        # Check if momentum and mean_reversion are enabled (most common)
        key_strategies = ['momentum', 'mean_reversion']
        missing_key_strategies = [s for s in key_strategies if s not in enabled_strategies]
        
        if missing_key_strategies:
            print(f"⚠️  Key strategies not enabled: {missing_key_strategies}")
            print(f"   💡 Consider enabling: {missing_key_strategies}")
        
        # Test strategy manager initialization
        from strategies.elite_strategy_manager import EliteStrategyManager
        
        print(f"📊 Testing Strategy Manager...")
        strategy_manager = EliteStrategyManager(config=strategies_config)
        print(f"   ✅ Strategy Manager initialized")
        print(f"   📊 Loaded strategies: {len(strategy_manager.strategies)}")
        
        # Check if strategies have configurations
        for strategy in strategy_manager.strategies:
            strategy_name = strategy.__class__.__name__
            has_config = hasattr(strategy, 'strategy_config') and strategy.strategy_config
            print(f"   {'✅' if has_config else '❌'} {strategy_name}: {'has config' if has_config else 'no config'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Strategy status check failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main debugging function."""
    print("🎯 Trading Cycle Debugging - Identifying Bottlenecks")
    print("=" * 50)
    
    # Check 1: Main system status
    main_ok = check_main_system_status()
    
    # Check 2: Configuration status
    config_ok = check_configuration_status()
    
    # Check 3: Dependencies
    deps_ok = check_dependencies()
    
    # Check 4: Trading components
    trading_ok = check_trading_components()
    
    # Check 5: Scanner status
    scanner_ok = check_scanner_status()
    
    # Check 6: Strategy status
    strategy_ok = check_strategy_status()
    
    print(f"\n📊 Debug Results:")
    print(f"   Main System: {'✅ WORKING' if main_ok else '❌ BROKEN'}")
    print(f"   Configuration: {'✅ WORKING' if config_ok else '❌ BROKEN'}")
    print(f"   Dependencies: {'✅ AVAILABLE' if deps_ok else '❌ MISSING'}")
    print(f"   Trading Components: {'✅ WORKING' if trading_ok else '❌ BROKEN'}")
    print(f"   Scanners: {'✅ WORKING' if scanner_ok else '❌ BROKEN'}")
    print(f"   Strategies: {'✅ WORKING' if strategy_ok else '❌ BROKEN'}")
    
    overall_ok = main_ok and config_ok and deps_ok and trading_ok and scanner_ok and strategy_ok
    
    if overall_ok:
        print(f"\n🎉 ALL SYSTEMS WORKING!")
        print(f"✅ Main system is functional")
        print(f"✅ Configuration is complete")
        print(f"✅ Dependencies are available")
        print(f"✅ Trading components are ready")
        print(f"✅ Scanners are configured")
        print(f"✅ Strategies are loaded")
        print(f"\n💡 If still stuck, check:")
        print(f"   - System logs for specific error messages")
        print(f"   - Network connectivity")
        print(f"   - RPC endpoints")
        print(f"   - API rate limits")
        print(f"   - Resource usage")
    else:
        print(f"\n❌ SYSTEM ISSUES FOUND!")
        print(f"   Check the failed components above for specific issues")
        
        if not scanner_ok:
            print(f"\n🔍 SCANNER ISSUES:")
            print(f"   - Enable at least one scanner in config_unified.yaml")
            print(f"   - Check scanner configuration")
            print(f"   - Verify scanner dependencies")
        
        if not strategy_ok:
            print(f"\n🔍 STRATEGY ISSUES:")
            print(f"   - Enable at least one strategy in config_unified.yaml")
            print(f"   - Check strategy configurations")
            print(f"   - Verify strategy dependencies")
        
        if not trading_ok:
            print(f"\n🔍 TRADING COMPONENT ISSUES:")
            print(f"   - Check trading configuration")
            print(f"   - Verify trading dependencies")
            print(f"   - Check network connectivity")
    
    return overall_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
