from .health_check import HealthStatus, standard_health_check

"""
API Key Manager - Centralized management of API keys for both paper and live modes.
"""
import os
from typing import Any, Dict, Optional

from config import load_config


class APIManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(APIManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.config = load_config()
        self._api_keys = {}
        self._load_api_keys()
        self._initialized = True
    
    def _load_api_keys(self):
        """Load API keys from config and environment."""
        # Initialize API keys from config
        self._api_keys = self.config.get('api_keys', {})
        
        # No environment variable override - use config only
    
    def get_key(self, service_name: str) -> Optional[str]:
        """Get API key for a specific service."""
        # Check config
        return self._api_keys.get(service_name.lower())
    
    def get_keys(self, service_name: str) -> Dict[str, Any]:
        """Get multiple API keys/credentials for a service."""
        keys = self._api_keys.get(service_name.lower(), {})
        if isinstance(keys, dict):
            return keys.copy()
        return {}
    
    def is_paper_mode(self) -> bool:
        """Check if running in paper trading mode."""
        return self.config.get('mode', 'paper').lower() == 'paper'
    
    def get_rpc_url(self, network: str) -> str:
        """Get RPC URL for the specified network."""
        # Check config
        config_url = self.config.get('networks', {}).get(network, {}).get('rpc')
        if config_url:
            return config_url
            
        return ''

# Singleton instance
api_manager = APIManager()

def get_api_key(service_name: str) -> Optional[str]:
    """Helper function to get an API key."""
    return api_manager.get_key(service_name)

def get_rpc_url(network: str) -> str:
    """Helper function to get an RPC URL."""
    return api_manager.get_rpc_url(network)

    @standard_health_check("API Manager")
    async def health_check(self) -> HealthStatus:
        """Check API key availability and validity."""
        required_services = ['alchemy', 'infura', 'etherscan']  # Example services
        missing_services = []
        invalid_services = []
        
        for service in required_services:
            key = self.get_key(service)
            if not key:
                missing_services.append(service)
            # Add additional validation if needed
            # elif not self._validate_api_key(service, key):
            #     invalid_services.append(service)
        
        is_healthy = not (missing_services or invalid_services)
        issues = []
        if missing_services:
            issues.append(f"Missing API keys: {', '.join(missing_services)}")
        if invalid_services:
            issues.append(f"Invalid API keys: {', '.join(invalid_services)}")
        
        return HealthStatus(
            component="API Manager",
            status=is_healthy,
            message=(
                "All API keys configured" if is_healthy 
                else "; ".join(issues)
            ),
            metrics={
                "status": "healthy" if is_healthy else "degraded",
                "total_services": len(required_services),
                "missing_services": missing_services,
                "invalid_services": invalid_services
            }
        )
