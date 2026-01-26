"""
Configuration migration tool.

This script helps migrate from the old configuration structure to the new one.
"""
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigMigrator:
    """Handles migration of configuration files."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the migrator.
        
        Args:
            config_dir: Directory containing config files. Defaults to the parent directory.
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent
        self.backup_dir = self.config_dir / 'backups'
        self.backup_dir.mkdir(exist_ok=True)
    
    def backup_file(self, file_path: Path) -> Path:
        """Create a backup of a file."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"{file_path.stem}_{timestamp}{file_path.suffix}"
        shutil.copy2(file_path, backup_path)
        return backup_path
    
    def load_yaml(self, file_path: Path) -> Dict[str, Any]:
        """Load a YAML file."""
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
            return {}
    
    def save_yaml(self, data: Dict[str, Any], file_path: Path) -> None:
        """Save data to a YAML file."""
        try:
            with open(file_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            print(f"Saved configuration to {file_path}")
        except Exception as e:
            print(f"Error saving {file_path}: {e}")
    
    def migrate_to_unified_config(self) -> bool:
        """Migrate to the new unified config structure."""
        print("Starting configuration migration...")
        
        # Check if we already have a unified config
        unified_config_path = self.config_dir / 'config.yaml'
        if unified_config_path.exists():
            print("Unified config already exists. Creating a backup first...")
            self.backup_file(unified_config_path)
        
        # Start with an empty config
        config = {
            'version': '1.0.0',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        }
        
        # Merge all config files
        config_files = [
            'trading_config.yaml',
            'scanner_config.yaml',
            'ai_config.yaml',
            'strategies.yaml',
            'auto_switch_config.yaml',
            'datasource.yaml'
        ]
        
        for config_file in config_files:
            file_path = self.config_dir / config_file
            if file_path.exists():
                print(f"Merging {config_file}...")
                config_data = self.load_yaml(file_path)
                self._deep_merge(config, config_data)
                
                # Create backup of the old file
                backup_path = self.backup_file(file_path)
                print(f"  - Backup created at {backup_path}")
                
                # Option to remove the old file
                if input(f"  Remove old file {config_file}? [y/N] ").lower() == 'y':
                    file_path.unlink()
                    print(f"  - Removed {config_file}")
        
        # Save the unified config
        self.save_yaml(config, unified_config_path)
        
        # Create .gitignore if it doesn't exist
        gitignore_path = self.config_dir.parent / '.gitignore'
        if not gitignore_path.exists():
            with open(gitignore_path, 'w') as f:
                f.write("# Configuration\nconfig.yaml\nconfig/*.yaml\n!config/*.example.yaml\n")
        
        print("\nMigration complete!")
        print(f"- Unified config created at {unified_config_path}")
        print(f"- Backups are stored in {self.backup_dir}")
        print("\nPlease review the new configuration and update any environment variables.")
        
        return True
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key] = self._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

def main():
    """Run the migration tool."""
    migrator = ConfigMigrator()
    
    print("=" * 50)
    print("Configuration Migration Tool")
    print("=" * 50)
    print("This tool will help migrate your configuration to the new unified format.\n")
    
    if input("Do you want to continue? [y/N] ").lower() != 'y':
        print("Migration cancelled.")
        return 1
    
    try:
        if migrator.migrate_to_unified_config():
            print("\nMigration completed successfully!")
            return 0
        else:
            print("\nMigration failed. Please check the error messages above.")
            return 1
    except Exception as e:
        print(f"\nAn error occurred during migration: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
