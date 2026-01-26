#!/usr/bin/env python3
"""
Configuration Cleanup Script
Safely removes redundant configuration files after unified config implementation.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path


def backup_file(filepath):
    """Create a backup of a file before removal."""
    if filepath.exists():
        backup_dir = Path("config/backups")
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{filepath.stem}_{timestamp}{filepath.suffix}"
        shutil.copy2(filepath, backup_path)
        print(f"📋 Backed up: {filepath} -> {backup_path}")
        return backup_path
    return None

def main():
    """Remove redundant configuration files safely."""
    
    config_dir = Path("config")
    
    # Files that can be safely removed (their content is now in config_unified.yaml)
    redundant_files = [
        "config.yaml",           # Superseded by config_unified.yaml
        "trading_config.yaml",   # Content merged into config_unified.yaml
        "ai_config.yaml",        # Content merged into config_unified.yaml
    ]
    
    # Files to keep (still needed)
    keep_files = [
        "networks.yaml",        # Chain-specific settings (not merged)
        "scanner_config.yaml",    # Scanner-specific settings (not merged)
        "config.template.yaml",  # Template file (reference)
        "config_unified.yaml",  # NEW unified config (keep!)
        "strategies.yaml",       # Strategy-specific settings (not merged)
        "ecosystem.yaml",       # Ecosystem-specific settings
        "datasource.yaml",       # Data source configuration
        "prometheus.yml",        # Monitoring configuration
    ]
    
    # Files that need manual review before removal
    review_files = [
        "config.py",             # Python config module (may have imports)
        "load_config.py",        # Config loading logic
        "migrate.py",           # Migration script (keep for reference)
        "validator.py",          # Config validation (may need updates)
    ]
    
    print("🧹 Configuration Cleanup Process")
    print("=" * 50)
    
    # Step 1: Backup redundant files
    print("\n📋 Step 1: Backing up redundant files...")
    for filename in redundant_files:
        filepath = config_dir / filename
        if filepath.exists():
            backup_file(filepath)
        else:
            print(f"⚠️  File not found: {filepath}")
    
    # Step 2: Remove redundant files
    print("\n🗑️  Step 2: Removing redundant files...")
    removed_count = 0
    for filename in redundant_files:
        filepath = config_dir / filename
        if filepath.exists():
            filepath.unlink()
            print(f"✅ Removed: {filepath}")
            removed_count += 1
        else:
            print(f"⚠️  File not found: {filepath}")
    
    # Step 3: Report kept files
    print(f"\n📁 Step 3: Files kept ({len(keep_files)} files)...")
    for filename in keep_files:
        filepath = config_dir / filename
        if filepath.exists():
            print(f"✅ Kept: {filepath}")
        else:
            print(f"⚠️  File not found: {filepath}")
    
    # Step 4: Report files needing review
    print(f"\n🔍 Step 4: Files needing manual review ({len(review_files)} files)...")
    for filename in review_files:
        filepath = config_dir / filename
        if filepath.exists():
            print(f"⚠️  Review needed: {filepath}")
        else:
            print(f"⚠️  File not found: {filepath}")
    
    # Step 5: Summary
    print("\n" + "=" * 50)
    print("📊 CLEANUP SUMMARY")
    print("=" * 50)
    print(f"✅ Files removed: {removed_count}")
    print(f"📁 Files kept: {len([f for f in keep_files if (config_dir / f).exists()])}")
    print(f"🔍 Files needing review: {len([f for f in review_files if (config_dir / f).exists()])}")
    
    # Step 6: Next steps
    print("\n📋 NEXT STEPS:")
    print("1. Update import statements to use config_unified.yaml")
    print("2. Review and update config.py and load_config.py")
    print("3. Test system with new unified configuration")
    print("4. Remove backup files once migration is verified")
    
    print(f"\n🎉 Cleanup completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
