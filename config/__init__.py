"""Configuration module for ecosystem trading platform."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List

# from .network_config import NetworkConfig

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

        # Normalize networks: older configs may list networks as a YAML list
        # Convert list entries into a mapping keyed by a slugified name so
        # callers can safely do `config['networks'].items()`.
        networks = config.get('networks')
        if isinstance(networks, list):
            import re

            def _slug(text: str) -> str:
                return re.sub(r"[^a-z0-9_]+", "_", text.strip().lower()).strip("_")

            normalized = {}
            for entry in networks:
                if not isinstance(entry, dict):
                    continue
                name = entry.get('name') or entry.get('network') or f"chain_{entry.get('chain_id', 'unknown')}"
                key = entry.get('key') or entry.get('id') or _slug(name)
                rpc = entry.get('rpc_primary') or entry.get('rpc') or entry.get('rpc_url')
                fallbacks = []
                for fk in ('rpc_fallback_1', 'rpc_fallback_2', 'rpc_fallback_3', 'fallback_rpcs'):
                    v = entry.get(fk)
                    if isinstance(v, list):
                        fallbacks.extend(v)
                    elif v:
                        fallbacks.append(v)

                node = {
                    'name': name,
                    'rpc': rpc,
                    'chain_id': entry.get('chain_id'),
                    'enabled': entry.get('execution_enabled', True),
                }
                if fallbacks:
                    node['fallback_rpcs'] = fallbacks
                normalized[key] = node

            config['networks'] = normalized

        # Add network config from NetworkConfig (excluding network info which comes from network_config.py)
        if 'network' not in config:
            config['network'] = {}
        
        print(f"✅ Loaded configuration from: {config_file}")
        return config
        
    except Exception as e:
        raise ConfigError(f"Failed to load configuration from {config_file}: {e}")

# Alias for backward compatibility
get_config = load_config

# Global config cache
_config_cache = None

def get_config_cached() -> Dict[str, Any]:
    """Get cached configuration or load if not cached."""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache

def is_network_supported(network_name: str) -> bool:
    """Check if a network is supported in the configuration."""
    try:
        config = get_config_cached()
        networks = config.get('networks', {})
        return network_name in networks
    except Exception:
        return False

def get_network_config(network_name: str) -> Dict[str, Any]:
    """Get configuration for a specific network."""
    try:
        config = get_config_cached()
        networks = config.get('networks', {})
        return networks.get(network_name, {})
    except Exception:
        return {}

def get_evm_networks() -> List[str]:
    """Get list of all EVM-compatible networks."""
    try:
        config = get_config_cached()
        networks = config.get('networks', {})
        return list(networks.keys())
    except Exception:
        return []

def get_chain_id(network_name: str) -> int:
    """Get chain ID for a specific network."""
    try:
        network_config = get_network_config(network_name)
        return network_config.get('chain_id')
    except Exception:
        return None

__all__ = [
    'ConfigError',
    # 'NetworkConfig',
    'load_config',
    'get_config',
    'is_network_supported',
    'get_network_config', 
    'get_evm_networks',
    'get_chain_id'
]
