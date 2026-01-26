#!/usr/bin/env python3
"""
Script to check paper trading mode detection
"""
import os
import sys
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_trading_mode():
    """Check trading mode detection"""
    print("🔍 CHECKING TRADING MODE DETECTION")
    print("=" * 50)
    
    # Load config
    config = {}
    config_files = [
        'config/config.yaml',
        'config/trading_config.yaml'
    ]
    
    for config_file in config_files:
        config_path = project_root / config_file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    if file_config:
                        config.update(file_config)
            except Exception as e:
                print(f"❌ Error loading {config_file}: {e}")
    
    # Check trading mode in config
    trading_config = config.get('trading', {})
    mode = trading_config.get('mode', 'not found')
    paper_trading = trading_config.get('paper_trading', False)
    
    print(f"📋 Config trading mode: {mode}")
    print(f"📋 Config paper_trading: {paper_trading}")
    
    # Simulate TradeExecutor logic
    print("\n🧪 SIMULATING TRADE EXECUTOR LOGIC:")
    
    # Check _is_paper_trading logic
    trading_mode_obj = None  # This would be passed to TradeExecutor
    
    # Simulate the _is_paper_trading method
    if trading_mode_obj and hasattr(trading_mode_obj, 'is_paper'):
        paper_trading_detected = trading_mode_obj.is_paper()
        print(f"   Using trading_mode.is_paper(): {paper_trading_detected}")
    else:
        paper_trading_detected = trading_config.get('paper_trading', False)
        print(f"   Using config paper_trading: {paper_trading_detected}")
    
    print(f"\n🎯 FINAL PAPER TRADING DETECTION: {paper_trading_detected}")
    
    # Check if there are any environment overrides
    print(f"\n🌍 ENVIRONMENT CHECK:")
    print(f"   TRADING_MODE: {os.getenv('TRADING_MODE', 'not set')}")
    print(f"   PAPER_TRADING: {os.getenv('PAPER_TRADING', 'not set')}")
    
    # The issue might be that 'mode' is 'paper' but 'paper_trading' flag is not set
    if mode.lower() == 'paper' and not paper_trading:
        print(f"\n⚠️  ISSUE DETECTED!")
        print(f"   Mode is set to 'paper' but paper_trading flag is False")
        print(f"   TradeExecutor may not detect paper mode correctly")
        print(f"   Solution: Set paper_trading: true in config")

if __name__ == "__main__":
    check_trading_mode()
