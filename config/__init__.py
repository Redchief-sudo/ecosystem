"""Configuration module for ecosystem trading platform."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any

from .network_config import NetworkConfig

class ConfigError(Exception):
    """Configuration related errors."""
    pass

def load_config() -> Dict[str, Any]:
    """Load unified configuration from config_unified.yaml."""
    # Look for config_unified.yaml in several locations
    config_paths = [
        Path(__file__).parent / 'config_unified.yaml',
        Path(__file__).parent.parent / 'config_unified.yaml',
        Path(__file__).parent / 'config.yaml',
        Path(__file__).parent.parent / 'config.yaml',
    ]
    
    config_file = None
    for path in config_paths:
        if path.exists():
            config_file = path
            break
    
    if not config_file:
        # Fallback to template if no config found
        template_path = Path(__file__).parent / 'config.template.yaml'
        if template_path.exists():
            print(f"⚠️  No config_unified.yaml found, using template: {template_path}")
            config_file = template_path
        else:
            raise ConfigError("No configuration file found. Please create config_unified.yaml")
    
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Ensure basic structure
        if not config:
            config = {}
        
        # Add network config from NetworkConfig (excluding network info which comes from network_config.py)
        if 'network' not in config:
            config['network'] = {}
        
        print(f"✅ Loaded configuration from: {config_file}")
        return config
        
    except Exception as e:
        raise ConfigError(f"Failed to load configuration from {config_file}: {e}")

__all__ = [
    'ConfigError',
    'NetworkConfig',
    'load_config'
]
