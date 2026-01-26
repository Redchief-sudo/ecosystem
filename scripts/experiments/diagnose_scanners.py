#!/usr/bin/env python3
"""
Scanner Diagnostic Script
This script checks scanner files, imports, and configuration to identify
why the system might be running without scanners.
"""

import sys
import os
import asyncio
import importlib

# Add home/damien/ecosystem to path
sys.path.insert(0, '/home/damien/ecosystem')

def check_scanner_files():
    """Check which scanner files exist in the discovery directory."""
    print("=" * 80)
    print("SCANNER FILES CHECK")
    print("=" * 80)
    
    scanner_dir = '/home/damien/ecosystem/scanners/discovery'
    expected_files = [
        'ai_discovery_scanner.py',
        'dex_guru_scanner.py', 
        'dex_screener_scanner.py',
        'dexscreener_scanner.py',
        'mempool_scanner.py',
        'onchain_scanner.py',
        'sentiment_scanner.py',
        'sentiment_scanner_integration.py',
    ]
    
    existing_files = os.listdir(scanner_dir)
    print(f"\nFiles in {scanner_dir}:")
    for f in sorted(existing_files):
        if f.endswith('.py'):
            print(f"  ✓ {f}")
    
    print("\nExpected scanner files:")
    for f in expected_files:
        exists = f in existing_files
        status = "✓ EXISTS" if exists else "✗ MISSING"
        print(f"  {status}: {f}")
    
    return existing_files

def check_scanner_classes(file_list):
    """Try to import scanner classes and check if they exist."""
    print("\n" + "=" * 80)
    print("SCANNER CLASS IMPORT CHECK")
    print("=" * 80)
    
    scanner_classes = {
        'scanners.discovery.ai_discovery_scanner': ['AIDiscoveryScanner'],
        'scanners.discovery.dex_guru_scanner': ['DexGuruScanner'],
        'scanners.discovery.dex_screener_scanner': ['DexScreenerScanner'],
        'scanners.discovery.dexscreener_scanner': ['DexScreenerUltraScanner'],
        'scanners.discovery.mempool_scanner': ['MempoolScannerUltra'],
        'scanners.discovery.onchain_scanner': ['OnChainScannerUltra'],
        'scanners.discovery.sentiment_scanner': ['SentimentScanner'],
    }
    
    results = {}
    for module_path, class_names in scanner_classes.items():
        print(f"\nModule: {module_path}")
        try:
            module = importlib.import_module(module_path)
            for class_name in class_names:
                if hasattr(module, class_name):
                    cls = getattr(module, class_name)
                    print(f"  ✓ {class_name}: Found")
                    results[f"{module_path}.{class_name}"] = True
                else:
                    print(f"  ✗ {class_name}: NOT FOUND")
                    results[f"{module_path}.{class_name}"] = False
        except ImportError as e:
            print(f"  ✗ Module import failed: {e}")
            for class_name in class_names:
                results[f"{module_path}.{class_name}"] = False
    
    return results

def check_config_scanner_section():
    """Check the scanner configuration in config_unified.yaml."""
    print("\n" + "=" * 80)
    print("SCANNER CONFIGURATION CHECK")
    print("=" * 80)
    
    import yaml
    
    config_path = '/home/damien/ecosystem/config/config_unified.yaml'
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check if scanner section exists
        if 'scanner' in config:
            scanner_cfg = config['scanner']
            print(f"\n✓ 'scanner' section found in config")
            print(f"  Keys: {list(scanner_cfg.keys())}")
            
            if 'scanners' in scanner_cfg:
                scanners = scanner_cfg['scanners']
                print(f"\n  Configured scanners ({len(scanners)}):")
                for name, cfg in scanners.items():
                    enabled = cfg.get('enabled', True) if isinstance(cfg, dict) else True
                    class_path = cfg.get('class', 'N/A') if isinstance(cfg, dict) else 'N/A'
                    status = "ENABLED" if enabled else "DISABLED"
                    print(f"    - {name}: {status}")
                    print(f"      Class: {class_path}")
            else:
                print(f"\n  ✗ No 'scanners' subsection found")
        else:
            print(f"\n  ✗ No 'scanner' section found in config")
            # Check for alternative structure
            if 'scanners' in config:
                print(f"  Found 'scanners' at top level")
                scanners = config['scanners']
                for name, cfg in scanners.items():
                    print(f"    - {name}: {cfg}")
        
        return config.get('scanner', {})
        
    except Exception as e:
        print(f"Error loading config: {e}")
        return None

def check_scan_director_init():
    """Test ScanDirector initialization logic."""
    print("\n" + "=" * 80)
    print("SCAN DIRECTOR INITIALIZATION CHECK")
    print("=" * 80)
    
    from scanners.scan_director import ScanDirector
    import inspect
    
    # Check _initialize_scanners method
    init_method = ScanDirector._initialize_scanners
    source = inspect.getsource(init_method)
    
    print("\nKey checks in _initialize_scanners():")
    
    # Check for built_in_scanners dict
    if 'built_in_scanners' in source:
        print("  ✓ built_in_scanners dict found")
        # Extract the dict
        import re
        match = re.search(r'built_in_scanners = \{([^}]+)\}', source, re.DOTALL)
        if match:
            print(f"  Built-in scanners: {match.group(0)[:200]}...")
    else:
        print("  ✗ built_in_scanners dict NOT found")
    
    # Check for scanner_configs extraction
    if 'scanner_configs = scanner_config.get("scanners"' in source:
        print("  ✓ Scanner config extraction found")
    else:
        print("  ✗ Scanner config extraction NOT found")
    
    # Check _check_scanner_capability_gating
    gating_method = ScanDirector._check_scanner_capability_gating
    gating_source = inspect.getsource(gating_method)
    
    print("\n  Capability gating checks:")
    if 'get_token_availability_status' in gating_source:
        print("    ✓ Token availability check found")
    else:
        print("    ✗ Token availability check NOT found")
    
    if 'has_tokens' in gating_source:
        print("    ✓ has_tokens check found")
    else:
        print("    ✗ has_tokens check NOT found")
    
    return True

def check_network_manager():
    """Check network manager status."""
    print("\n" + "=" * 80)
    print("NETWORK MANAGER STATUS CHECK")
    print("=" * 80)
    
    try:
        from config.config_loader import load_config
        config = load_config()
        
        # Check networks section
        if 'networks' in config:
            networks = config['networks']
            print(f"\n✓ Networks section found: {len(networks)} networks")
            
            # Check enabled networks
            enabled = []
            for name, cfg in networks.items():
                if isinstance(cfg, dict):
                    enabled_val = cfg.get('enabled', True)
                    if enabled_val:
                        enabled.append(name)
            
            print(f"  Enabled networks: {len(enabled)}")
            print(f"  Networks: {enabled[:10]}...")  # Show first 10
        else:
            print("\n✗ No networks section found")
            
    except Exception as e:
        print(f"\nError checking network manager: {e}")
    
    return True

def check_memory_token_status():
    """Check memory token availability."""
    print("\n" + "=" * 80)
    print("MEMORY TOKEN STATUS CHECK")
    print("=" * 80)
    
    try:
        from utils.memory import MemoryManager
        memory = MemoryManager()
        
        print("\nMemoryManager initialized")
        
        # Check if get_token_availability_status exists
        if hasattr(memory, 'get_token_availability_status'):
            print("  ✓ get_token_availability_status method exists")
            try:
                status = memory.get_token_availability_status()
                print(f"  Status: {status}")
            except Exception as e:
                print(f"  ✗ Error getting token status: {e}")
        else:
            print("  ✗ get_token_availability_status method NOT found")
        
        # Check if tokens exist
        if hasattr(memory, 'tokens'):
            print(f"  ✓ tokens attribute exists")
            print(f"    Type: {type(memory.tokens)}")
            print(f"    Length: {len(memory.tokens) if hasattr(memory.tokens, '__len__') else 'N/A'}")
        else:
            print("  ✗ tokens attribute NOT found")
            
    except Exception as e:
        print(f"\nError checking memory: {e}")
        import traceback
        traceback.print_exc()
    
    return True

async def run_full_diagnostic():
    """Run all diagnostic checks."""
    print("\n" + "=" * 80)
    print("SCANNER SYSTEM DIAGNOSTIC REPORT")
    print("=" * 80)
    
    # Run all checks
    file_list = check_scanner_files()
    class_results = check_scanner_classes(file_list)
    config_results = check_config_scanner_section()
    scan_director_results = check_scan_director_init()
    network_results = check_network_manager()
    memory_results = check_memory_token_status()
    
    # Summary
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    
    missing_classes = [k for k, v in class_results.items() if not v]
    
    if missing_classes:
        print("\n⚠️  MISSING SCANNER CLASSES:")
        for cls in missing_classes:
            print(f"  - {cls}")
        print("\nThis is likely why scanners are not running!")
    else:
        print("\n✓ All scanner classes found")
    
    if not config_results:
        print("\n⚠️  No scanner configuration found - check config structure")
    else:
        print("\n✓ Scanner configuration exists")
    
    print("\n" + "=" * 80)
    print("RECOMMENDED ACTIONS")
    print("=" * 80)
    
    if missing_classes:
        print("\n1. CREATE MISSING SCANNER FILES:")
        for cls in missing_classes:
            module_path = cls.rsplit('.', 1)[0]
            file_path = f"/home/damien/ecosystem/{module_path.replace('.', '/')}.py"
            print(f"   Create: {file_path}")
    
    print("\n2. Or update config_unified.yaml to use existing scanner classes")
    print("   Available classes in scanners/discovery/:")
    for f in file_list:
        if f.endswith('.py') and not f.startswith('__'):
            class_name = f.replace('.py', '').replace('_', ' ').title().replace(' ', '')
            print(f"   - {class_name}")
    
    return {
        'missing_classes': missing_classes,
        'config_exists': config_results is not None
    }

if __name__ == "__main__":
    results = asyncio.run(run_full_diagnostic())
    
    # Exit with error code if issues found
    if results['missing_classes'] or not results['config_exists']:
        sys.exit(1)
    sys.exit(0)

