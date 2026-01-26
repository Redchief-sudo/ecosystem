"""
API Utilities - Centralized API key and configuration management.
"""
import os
from typing import Any, Dict, Optional, Union

from config import load_config


class APIConfig:
    """Centralized API configuration manager."""
    
    def __init__(self):
        self.config = load_config()
        self._api_keys = self._load_api_keys()
    
    def _load_api_keys(self) -> Dict[str, Any]:
        """Load API keys with environment variable overrides."""
        # Get base config
        keys = self.config.get('api_keys', {})
        
        # Apply environment variable overrides
        for key in list(keys.keys()):
            env_key = f"{key.upper()}_API_KEY"
            if env_key in os.environ:
                keys[key] = os.environ[env_key]
        
        # Handle nested configurations (like exchange credentials)
        for key, value in keys.items():
            if isinstance(value, dict):
                keys[key] = self._load_nested_config(value, key)
        
        return keys
    
    def _load_nested_config(self, config_dict: Dict[str, Any], prefix: str) -> Dict[str, Any]:
        """Load nested configuration from dictionary."""
        result = {}
        for k, v in config_dict.items():
            if isinstance(v, dict):
                result[k] = self._load_nested_config(v, f"{prefix}_{k}")
            else:
                # Use config value directly, no environment variable
                result[k] = v
        return result
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get API key or config value."""
        # Check config only
        return self.config.get(key, default)
    
    def get_credentials(self, service: str) -> Dict[str, Any]:
        """Get all credentials for a service."""
        creds = self._api_keys.get(service, {})
        if not isinstance(creds, dict):
            return {"api_key": creds}
        return creds
    
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode."""
        return self.config.get('mode', 'paper').lower() == 'paper'
    
    def get_rpc_url(self, network: str) -> str:
        """Get RPC URL for the specified network."""
        # Check config only
        config_url = self.config.get('networks', {}).get(network, {}).get('rpc')
        if config_url:
            return config_url
            
        return ''

# Global instance
api_config = APIConfig()

def get_api_key(service: str) -> Optional[str]:
    """Get API key for a service."""
    return api_config.get(service)

def get_credentials(service: str) -> Dict[str, Any]:
    """Get all credentials for a service."""
    return api_config.get_credentials(service)

def is_paper_mode() -> bool:
    """Check if running in paper trading mode."""
    return api_config.is_paper_mode()

def get_rpc_url(network: str) -> str:
    """Get RPC URL for a network."""
    return api_config.get_rpc_url(network)
