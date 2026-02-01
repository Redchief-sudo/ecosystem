"""
Configuration validation utilities for the trading system.
"""
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)

class ConfigValidator:
    """Validates the configuration file and environment variables."""
    
    @classmethod
    def validate_token_address(cls, address: str, network: str) -> bool:
        """Validate token address format for specific network"""
        # Implementation needed
        pass
    
    REQUIRED_SECTIONS = [
        'networks', 
        'trading',
        'scanners',
        'database'
    ]
    
    REQUIRED_ENV_VARS = [
        'ETH_RPC_URL',
        'BSC_RPC_URL',
        'POLYGON_RPC_URL',
        'ETHERSCAN_API_KEY',
        'BSCSCAN_API_KEY'
    ]
    
    @classmethod
    def validate_config_structure(cls, config: Dict[str, Any]) -> List[str]:
        """Validate the structure of the config file."""
        errors = []
        
        # Check required sections
        for section in cls.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Check required network configurations
        if 'networks' in config:
            required_networks = ['ethereum', 'bsc']  # Minimum required networks
            for network in required_networks:
                if network not in config['networks']:
                    errors.append(f"Missing required network configuration: {network}")
        
        return errors
    
    @classmethod
    def validate_environment(cls) -> List[str]:
        """Validate that all required environment variables are set."""
        missing_vars = [var for var in cls.REQUIRED_ENV_VARS if not os.getenv(var)]
        return missing_vars
    
    @classmethod
    def load_and_validate_config(cls, config_path: str) -> Dict[str, Any]:
        """Load and validate the configuration file."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            # Check config structure
            structure_errors = cls.validate_config_structure(config)
            if structure_errors:
                raise ValueError("\n".join(["Configuration validation failed:"] + structure_errors))
            
            # Check environment variables unless explicitly running in paper/simulation mode
            trading_mode = (
                config.get('trading', {})
                .get('trading_mode', '')
                .strip()
                .lower()
            )
            is_paper = trading_mode == 'paper'

            if not is_paper:
                missing_vars = cls.validate_environment()
                if missing_vars:
                    raise EnvironmentError(
                        f"Missing required environment variables: {', '.join(missing_vars)}"
                    )

            return config
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file: {e}")

    @classmethod
    def ensure_data_directories_exist(cls, base_path: str = 'data') -> None:
        """Ensure all required data directories exist."""
        directories = [
            base_path,
            f"{base_path}/cache",
            f"{base_path}/backups"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def validate_loaded_config(cls, config: Dict[str, Any]) -> List[str]:
        """Validate the loaded configuration structure and return errors."""
        errors = []
        
        # Check required sections
        for section in cls.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        # Check networks configuration
        if 'networks' in config:
            required_networks = ['ethereum', 'bsc']  # Minimum required networks
            for network in required_networks:
                if network not in config['networks']:
                    errors.append(f"Missing required network configuration: {network}")
        
        # Check trading configuration
        if 'trading' in config:
            trading = config['trading']
            # Check if wallets exist at root level (from trading_config.yaml)
            if 'wallets' not in config:
                errors.append("Missing 'wallets' configuration (expected at root level from trading_config.yaml)")
            elif 'executor' not in config['wallets']:
                errors.append("Missing 'executor' wallet configuration")
            # Add more wallet validation as needed
        else:
            errors.append("Missing 'trading' configuration")
        
        # Check scanner configuration
        if 'scanners' in config:
            scanners = config['scanners']
            if not scanners or not isinstance(scanners, dict):
                errors.append("Scanner configuration must be a dictionary with scanner definitions")
            else:
                # Check if at least one scanner is enabled
                enabled_scanners = [name for name, config in scanners.items() 
                                 if config.get('enabled', False)]
                if not enabled_scanners:
                    errors.append("No scanners are enabled. At least one scanner must be enabled.")
                else:
                    logger.info(f"Found {len(enabled_scanners)} enabled scanners: {enabled_scanners}")
        else:
            errors.append("Missing 'scanners' configuration")
        
        # Check database configuration
        if 'database' in config:
            if 'path' not in config['database']:
                errors.append("Missing database path configuration")
            # Add more database validation
        
        return errors
