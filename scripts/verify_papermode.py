#!/usr/bin/env python3
"""
Script to verify papermode status and logging configuration
"""
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_papermode_config():
    """Check if papermode is properly configured"""
    print("🔍 CHECKING PAPERMODE CONFIGURATION")
    print("=" * 50)
    
    # Check main config
    config_files = [
        'config/config.yaml',
        'config/trading_config.yaml'
    ]
    
    papermode_status = "UNKNOWN"
    
    for config_file in config_files:
        config_path = project_root / config_file
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = yaml.safe_load(f)
                
                # Check trading mode
                trading_config = config.get('trading', {})
                mode = trading_config.get('mode', 'not found')
                
                print(f"📄 {config_file}:")
                print(f"   Trading mode: {mode}")
                
                if mode.lower() == 'paper':
                    papermode_status = "PAPER"
                    print("   ✅ PAPERMODE ENABLED")
                elif mode.lower() == 'live':
                    papermode_status = "LIVE"
                    print("   ⚠️  LIVE MODE - REAL TRADING")
                else:
                    print(f"   ❓ Unknown mode: {mode}")
                
                # Check paper trading requirements
                min_trades = trading_config.get('min_paper_trades')
                min_success = trading_config.get('min_success_rate')
                
                # Validate configuration - fail fast if missing
                if min_trades is None:
                    print(f"   ❌ Missing required config: min_paper_trades")
                    continue
                if min_success is None:
                    print(f"   ❌ Missing required config: min_success_rate")
                    continue
                
                print(f"   Min paper trades: {min_trades}")
                print(f"   Min success rate: {min_success}")
                print()
                
            except Exception as e:
                print(f"   ❌ Error reading {config_file}: {e}")
                print()
    
    return papermode_status

def check_logging_setup():
    """Check logging configuration and files"""
    print("🔍 CHECKING LOGGING SETUP")
    print("=" * 50)
    
    logs_dir = project_root / 'logs'
    
    if not logs_dir.exists():
        print("❌ Logs directory does not exist")
        return False
    
    print(f"📁 Logs directory: {logs_dir}")
    print(f"   Directory exists: ✅")
    
    # Check log files
    log_files = [
        'ecosystem.log',
        'trading_bot.log', 
        'trading.log'
    ]
    
    for log_file in log_files:
        log_path = logs_dir / log_file
        if log_path.exists():
            size = log_path.stat().st_size
            mtime = datetime.fromtimestamp(log_path.stat().st_mtime)
            print(f"   📄 {log_file}: {size:,} bytes, modified {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"   ❌ {log_file}: Not found")
    
    # Check logging config
    main_config = project_root / 'config' / 'config.yaml'
    if main_config.exists():
        try:
            with open(main_config, 'r') as f:
                config = yaml.safe_load(f)
            
            logging_config = config.get('logging', {})
            print(f"\n📋 Logging configuration:")
            
            # Validate logging configuration
            if not logging_config:
                print(f"   ❌ No logging configuration found")
                return
            
            level = logging_config.get('level')
            file = logging_config.get('file')
            max_size = logging_config.get('max_size')
            backup_count = logging_config.get('backup_count')
            
            print(f"   Level: {level if level else '❌ NOT SET'}")
            print(f"   File: {file if file else '❌ NOT SET'}")
            print(f"   Max size: {max_size if max_size else '❌ NOT SET'} MB")
            print(f"   Backup count: {backup_count if backup_count else '❌ NOT SET'}")
            
        except Exception as e:
            print(f"   ❌ Error reading logging config: {e}")
    
    return True

def check_system_status():
    """Check if system is currently running"""
    print("🔍 CHECKING SYSTEM STATUS")
    print("=" * 50)
    
    # Check for main.py process
    try:
        import subprocess
        result = subprocess.run(['pgrep', '-f', 'python.*main\\.py'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"✅ System running - Found {len(pids)} process(es): {', '.join(pids)}")
            return True
        else:
            print("❌ System not running - No main.py process found")
            return False
    except Exception as e:
        print(f"❌ Error checking process status: {e}")
        return False

def check_recent_logs():
    """Check recent log entries for papermode confirmation"""
    print("🔍 CHECKING RECENT LOG ENTRIES")
    print("=" * 50)
    
    logs_dir = project_root / 'logs'
    log_files = ['ecosystem.log', 'trading_bot.log']
    
    for log_file in log_files:
        log_path = logs_dir / log_file
        if log_path.exists() and log_path.stat().st_size > 0:
            print(f"\n📄 Recent entries from {log_file}:")
            try:
                with open(log_path, 'r') as f:
                    lines = f.readlines()
                    # Get last 10 lines
                    recent_lines = lines[-10:] if len(lines) > 10 else lines
                
                for line in recent_lines:
                    # Look for paper/paper trading references
                    if any(keyword in line.lower() for keyword in ['paper', 'mode', 'trading']):
                        print(f"   {line.strip()}")
                    
            except Exception as e:
                print(f"   ❌ Error reading {log_file}: {e}")

def main():
    """Main verification function"""
    print("🚀 ECOSYSTEM PAPERMODE & LOGGING VERIFICATION")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check papermode configuration
    papermode_status = check_papermode_config()
    
    # Check logging setup
    logging_ok = check_logging_setup()
    
    # Check system status
    system_running = check_system_status()
    
    # Check recent logs
    check_recent_logs()
    
    # Summary
    print("\n📊 VERIFICATION SUMMARY")
    print("=" * 50)
    print(f"Papermode Status: {papermode_status}")
    print(f"Logging Setup: {'✅ OK' if logging_ok else '❌ ISSUES'}")
    print(f"System Running: {'✅ YES' if system_running else '❌ NO'}")
    
    if papermode_status == "PAPER":
        print("\n✅ SYSTEM IS CONFIGURED FOR PAPER TRADING")
    elif papermode_status == "LIVE":
        print("\n⚠️  SYSTEM IS CONFIGURED FOR LIVE TRADING - BE CAREFUL!")
    else:
        print("\n❓ COULD NOT DETERMINE TRADING MODE")
    
    if not system_running:
        print("\n💡 To start the system: python main.py")
    else:
        print("\n💡 System is currently running")

if __name__ == "__main__":
    main()
