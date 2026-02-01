#!/usr/bin/env python3
"""
Fingerprint verification script for CI/CD pipeline.

Verifies that fingerprints are present, valid, and can be generated
from the current configuration.
"""

import sys
from pathlib import Path

def main():
    """Main verification function."""
    print("=" * 60)
    print("FINGERPRINT VERIFICATION FOR CI/CD")
    print("=" * 60)
    print()
    
    # Check fingerprint module exists
    if not Path("core/fingerprint.py").exists():
        print("❌ FAIL: core/fingerprint.py not found")
        return 1
    print("✅ Fingerprint module exists")
    
    # Test fingerprint import
    try:
        from core.fingerprint import (
            generate_fingerprint,
            validate_fingerprint,
            EcosystemFingerprint,
            FingerprintVersion
        )
        print("✅ Fingerprint module imports successfully")
    except ImportError as e:
        print(f"❌ FAIL: Cannot import fingerprint module: {e}")
        return 1
    
    # Load config and generate fingerprint
    try:
        from config import load_config
        config = load_config()
        print("✅ Config loaded successfully")
    except Exception as e:
        print(f"❌ FAIL: Cannot load config: {e}")
        return 1
    
    # Generate fingerprint
    try:
        fingerprint = generate_fingerprint(config)
        print(f"✅ Fingerprint generated: {fingerprint.composite_hash[:16]}...")
    except Exception as e:
        print(f"❌ FAIL: Cannot generate fingerprint: {e}")
        return 1
    
    # Validate fingerprint
    try:
        is_valid = validate_fingerprint(fingerprint)
        if not is_valid:
            print("❌ FAIL: Fingerprint validation failed")
            return 1
        print("✅ Fingerprint is valid")
    except Exception as e:
        print(f"❌ FAIL: Fingerprint validation error: {e}")
        return 1
    
    # Verify fingerprint components
    if not fingerprint.creator:
        print("❌ FAIL: Creator fingerprint missing")
        return 1
    if not fingerprint.guardian:
        print("❌ FAIL: Guardian fingerprint missing")
        return 1
    if not fingerprint.behavioral:
        print("❌ FAIL: Behavioral fingerprint missing")
        return 1
    print("✅ All fingerprint components present")
    
    # Verify fingerprint integrity
    if not fingerprint.verify_integrity():
        print("❌ FAIL: Fingerprint integrity check failed")
        return 1
    print("✅ Fingerprint integrity verified")
    
    # Output fingerprint details
    fp_dict = fingerprint.to_dict()
    print()
    print("Fingerprint Details:")
    print(f"  Version: {fp_dict['fingerprint_version']}")
    print(f"  System ID: {fp_dict['creator']['system_id']}")
    print(f"  Networks: {fp_dict['creator']['network_count']}")
    print(f"  Strategies: {fp_dict['creator']['strategy_count']}")
    print(f"  Security Level: {fp_dict['guardian']['security_level']}")
    print(f"  Execution Mode: {fp_dict['behavioral']['execution_mode']}")
    print(f"  Composite Hash: {fp_dict['composite_hash'][:32]}...")
    
    print()
    print("=" * 60)
    print("✅ FINGERPRINT VERIFICATION PASSED")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
