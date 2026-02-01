"""
Network Manager Integration
Provides network management functionality for scanners
"""

import logging
from typing import Dict, Optional, Any
from pathlib import Path

import yaml
from web3 import Web3

logger = logging.getLogger(__name__)


class NetworkConfigManager:
    """
    Network configuration manager that bridges config_unified.yaml with NetworkManager
    """
    
    def __init__(self, config_path: str = "config/config_unified.yaml"):
        self.config_path = Path(config_path)
        self.networks_config: Dict[str, Any] = {}
        self.web3_connections: Dict[str, Web3] = {}
        self.load_config()
    
    def load_config(self):
        """Load network configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.networks_config = config.get('networks', {})
            logger.info(f"Loaded {len(self.networks_config)} network configurations")
            
        except Exception as e:
            logger.error(f"Failed to load network config: {e}")
            self.networks_config = {}
    
    def get_network(self, network_name: str) -> Optional[Dict[str, Any]]:
        """Get network configuration by name"""
        return self.networks_config.get(network_name)
    
    def get_chain_id(self, network_name: str) -> Optional[int]:
        """Get chain ID for a network"""
        network = self.get_network(network_name)
        return network.get('chain_id') if network else None
    
    def get_rpc_url(self, network_name: str) -> Optional[str]:
        """Get RPC URL for a network"""
        network = self.get_network(network_name)
        return network.get('rpc') if network else None
    
    def get_web3_connection(self, network_name: str) -> Optional[Web3]:
        """Get or create Web3 connection for a network"""
        if network_name not in self.web3_connections:
            rpc_url = self.get_rpc_url(network_name)
            if rpc_url:
                try:
                    self.web3_connections[network_name] = Web3(Web3.HTTPProvider(rpc_url))
                    logger.info(f"Created Web3 connection for {network_name}")
                except Exception as e:
                    logger.error(f"Failed to create Web3 connection for {network_name}: {e}")
        
        return self.web3_connections.get(network_name)
    
    def get_supported_networks(self) -> list:
        """Get list of supported network names"""
        return list(self.networks_config.keys())
    
    def is_network_supported(self, network_name: str) -> bool:
        """Check if a network is supported"""
        return network_name in self.networks_config
    
    def get_network_list(self) -> Dict[str, Any]:
        """Get all network configurations"""
        return self.networks_config.copy()


# Create a global instance
network_config_manager = NetworkConfigManager()

# Create a compatibility layer that provides both NetworkManager and config access
class IntegratedNetworkManager:
    """
    Integrated network manager that provides both NetworkManager functionality
    and direct access to network configurations
    """
    
    def __init__(self):
        self.config_manager = network_config_manager
        # Try to import the actual NetworkManager from networks package
        try:
            from networks import NetworkManager as ActualNetworkManager
            from networks import network_manager as actual_network_manager
            self.network_manager = actual_network_manager
            self.clients = getattr(actual_network_manager, 'clients', {})
        except ImportError:
            logger.warning("Could not import NetworkManager from networks package")
            self.network_manager = None
            self.clients = {}  # Fallback empty clients dict
    
    def get_network(self, network_name: str) -> Optional[Dict[str, Any]]:
        """Get network configuration"""
        return self.config_manager.get_network(network_name)
    
    def get_chain_id(self, network_name: str) -> Optional[int]:
        """Get chain ID"""
        return self.config_manager.get_chain_id(network_name)
    
    def get_rpc(self, network_name: str) -> Optional[str]:
        """Get RPC URL"""
        return self.config_manager.get_rpc_url(network_name)
    
    def get_web3(self, network_name: str) -> Optional[Web3]:
        """Get Web3 connection"""
        return self.config_manager.get_web3_connection(network_name)
    
    def get_supported_networks(self) -> list:
        """Get supported networks"""
        return self.config_manager.get_supported_networks()
    
    def is_network_supported(self, network_name: str) -> bool:
        """Check if network is supported"""
        return self.config_manager.is_network_supported(network_name)
    
    # Delegate to the actual NetworkManager for advanced functionality
    def __getattr__(self, name):
        """Delegate unknown attributes to the actual NetworkManager"""
        if self.network_manager:
            return getattr(self.network_manager, name)
        else:
            raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


# Create the integrated manager instance
integrated_network_manager = IntegratedNetworkManager()

# For backward compatibility, provide both managers
network_manager = integrated_network_manager  # This will be used by scanners
NetworkManager = type(integrated_network_manager)  # Class reference

# Export the main interface
__all__ = [
    'network_manager',
    'NetworkManager', 
    'NetworkConfigManager',
    'IntegratedNetworkManager',
    'integrated_network_manager'
]
