"""
Configuration validation for the trading bot.

This module provides validation for the configuration files to ensure
all required settings are present and valid.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import jsonschema
import yaml

from config import ConfigError


class ConfigValidator:
    """Validates configuration against a schema."""
    
    # Define the base schema that all configurations must follow
    BASE_SCHEMA = {
        "type": "object",
        "properties": {
            "version": {"type": "string"},
            "environment": {"type": "string", "enum": ["development", "staging", "production"]},
            "log_level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]},
        },
        "required": ["version", "environment"],
        "additionalProperties": True
    }
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the validator.
        
        Args:
            config_dir: Directory containing config files. Defaults to the parent directory.
        """
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent
        self.schemas = self._load_schemas()
    
    def _load_schemas(self) -> Dict[str, Dict]:
        """Load all schema definitions."""
        schemas = {
            'base': self.BASE_SCHEMA,
            'network': self._get_network_schema(),
            'ai': self._get_ai_schema(),
            'scanner': self._get_scanner_schema(),
            'strategy': self._get_strategy_schema()
        }
        return schemas
    
    def _get_network_schema(self) -> Dict:
        """Get schema for network configuration."""
        return {
            "type": "object",
            "properties": {
                "networks": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {
                            "type": "object",
                            "properties": {
                                "chain_id": {"type": "integer"},
                                "rpc": {"type": "string", "format": "uri"},
                                "wrapped_native": {"type": "string", "pattern": "^0x[a-fA-F0-9]{40}$"},
                                "enabled": {"type": "boolean"},
                                "min_gas_price": {"type": "number", "minimum": 0},
                                "max_gas_price": {"type": "number", "minimum": 0}
                            },
                            "required": ["chain_id", "rpc", "wrapped_native"]
                        }
                    }
                }
            }
        }
    
    def _get_ai_schema(self) -> Dict:
        """Get schema for AI configuration."""
        return {
            "type": "object",
            "properties": {
                "ai": {
                    "type": "object",
                    "properties": {
                        "enabled": {"type": "boolean"},
                        "min_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "models": {
                            "type": "object",
                            "patternProperties": {
                                ".*": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "input_features": {"type": "array", "items": {"type": "string"}},
                                        "output_features": {"type": "array", "items": {"type": "string"}}
                                    },
                                    "required": ["path", "input_features", "output_features"]
                                }
                            }
                        }
                    }
                }
            }
        }
    
    def _get_scanner_schema(self) -> Dict:
        """Get schema for scanner configuration."""
        return {
            "type": "object",
            "properties": {
                "scanners": {
                    "type": "object",
                    "properties": {
                        "default": {"$ref": "#/definitions/scanner_config"}
                    },
                    "patternProperties": {
                        ".*": {"$ref": "#/definitions/scanner_config"}
                    }
                }
            },
            "definitions": {
                "scanner_config": {
                    "type": "object",
                    "properties": {
                        "min_liquidity": {"type": "number", "minimum": 0},
                        "min_volume": {"type": "number", "minimum": 0},
                        "max_block_lag": {"type": "integer", "minimum": 1},
                        "enabled": {"type": "boolean"}
                    }
                }
            }
        }
    
    def _get_strategy_schema(self) -> Dict:
        """Get schema for strategy configuration."""
        return {
            "type": "object",
            "properties": {
                "strategies": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {
                            "type": "object",
                            "properties": {
                                "enabled": {"type": "boolean"},
                                "risk_per_trade": {"type": "number", "minimum": 0, "maximum": 1},
                                "max_position_size": {"type": "number", "minimum": 0, "maximum": 1},
                                "take_profit": {"type": "number", "minimum": 0},
                                "stop_loss": {"type": "number", "maximum": 0}
                            },
                            "required": ["enabled"]
                        }
                    }
                }
            }
        }
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate the configuration against all schemas.
        
        Args:
            config: The configuration to validate
            
        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []
        
        # First validate against base schema
        try:
            jsonschema.validate(instance=config, schema=self.schemas['base'])
        except jsonschema.ValidationError as e:
            errors.append(f"Base config validation failed: {e.message}")
        
        # Validate each section
        for section, schema in self.schemas.items():
            if section == 'base':
                continue
                
            try:
                jsonschema.validate(instance=config, schema=schema)
            except jsonschema.ValidationError as e:
                errors.append(f"{section} config validation failed: {e.message}")
        
        return len(errors) == 0, errors
    
    def validate_file(self, file_path: str) -> Tuple[bool, List[str]]:
        """Validate a configuration file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            Tuple of (is_valid, errors)
        """
        try:
            with open(file_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            return self.validate_config(config)
        except Exception as e:
            return False, [f"Failed to load config file: {str(e)}"]
    
    def validate_all(self) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate all configuration files in the config directory.
        
        Returns:
            Tuple of (all_valid, results) where results is a dict mapping
            filenames to lists of error messages
        """
        results = {}
        all_valid = True
        
        for config_file in self.config_dir.glob('*.yaml'):
            is_valid, errors = self.validate_file(config_file)
            results[config_file.name] = errors
            all_valid = all_valid and is_valid
        
        return all_valid, results

# Create a singleton instance
_validator = None
def get_validator() -> 'ConfigValidator':
    """Get the singleton validator instance."""
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator
