"""
Validation Utilities for Fallback Redaction
===========================================
Provides strict validation to eliminate problematic fallbacks that mask real issues.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FieldValidator:
    """Strict field validation to prevent silent fallbacks."""

    @staticmethod
    def require_field(data: Dict, field: str, context: str = "") -> Any:
        """Require a field to be present and not None.

        Args:
            data: Dictionary to check
            field: Field name to require
            context: Context for error messages

        Returns:
            The field value

        Raises:
            ValueError: If field is missing or None
        """
        if field not in data:
            raise ValueError(f"Missing required field '{field}' in {context}")
        if data[field] is None:
            raise ValueError(f"Required field '{field}' is None in {context}")
        return data[field]

    @staticmethod
    def require_fields(data: Dict, fields: List[str], context: str = "") -> Dict:
        """Require multiple fields to be present and not None.

        Args:
            data: Dictionary to check
            fields: List of field names to require
            context: Context for error messages

        Returns:
            Dictionary with only the required fields

        Raises:
            ValueError: If any field is missing or None
        """
        missing = []
        result = {}

        for field in fields:
            if field not in data:
                missing.append(field)
            elif data[field] is None:
                missing.append(field)
            else:
                result[field] = data[field]

        if missing:
            raise ValueError(f"Missing required fields {missing} in {context}")

        return result

    @staticmethod
    def validate_numeric_field(value: Any, field_name: str, min_val: Optional[float] = None,
                             max_val: Optional[float] = None, allow_zero: bool = True) -> float:
        """Validate a numeric field with strict requirements.

        Args:
            value: Value to validate
            field_name: Field name for error messages
            min_val: Minimum allowed value (inclusive)
            max_val: Maximum allowed value (inclusive)
            allow_zero: Whether zero is allowed

        Returns:
            Validated float value

        Raises:
            ValueError: If validation fails
        """
        if value is None:
            raise ValueError(f"Field '{field_name}' cannot be None")

        try:
            numeric_value = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"Field '{field_name}' must be numeric, got {type(value)}: {value}")

        if not allow_zero and numeric_value == 0:
            raise ValueError(f"Field '{field_name}' cannot be zero")

        if min_val is not None and numeric_value < min_val:
            raise ValueError(f"Field '{field_name}' must be >= {min_val}, got {numeric_value}")

        if max_val is not None and numeric_value > max_val:
            raise ValueError(f"Field '{field_name}' must be <= {max_val}, got {numeric_value}")

        return numeric_value


class DataValidator:
    """Validation for data structures used in trading."""

    @staticmethod
    def validate_token_metrics(data: Dict, context: str = "token_metrics") -> Dict:
        """Validate required token metrics for trading decisions.

        Args:
            data: Token metrics dictionary
            context: Context for error messages

        Returns:
            Validated metrics dictionary

        Raises:
            ValueError: If required metrics are missing or invalid
        """
        required_metrics = ['price_usd', 'liquidity_usd', 'volume_24h']

        # Require all critical metrics
        validated = FieldValidator.require_fields(data, required_metrics, context)

        # Validate each metric is numeric and reasonable
        for metric in required_metrics:
            validated[metric] = FieldValidator.validate_numeric_field(
                validated[metric], metric, min_val=0, allow_zero=False
            )

        # Optional metrics with validation if present
        if 'market_cap' in data and data['market_cap'] is not None:
            validated['market_cap'] = FieldValidator.validate_numeric_field(
                data['market_cap'], 'market_cap', min_val=0, allow_zero=True
            )

        if 'volatility' in data and data['volatility'] is not None:
            validated['volatility'] = FieldValidator.validate_numeric_field(
                data['volatility'], 'volatility', min_val=0, max_val=10, allow_zero=True
            )

        return validated

    @staticmethod
    def validate_network_config(config: Dict, network: str) -> Dict:
        """Validate network configuration with no fallbacks.

        Args:
            config: Network configuration
            network: Network name

        Returns:
            Validated network config

        Raises:
            ValueError: If network config is incomplete
        """
        if network not in config:
            raise ValueError(f"Network '{network}' not configured")

        network_config = config[network]
        if not isinstance(network_config, dict):
            raise ValueError(f"Network '{network}' config must be a dictionary")

        # Require RPC URL
        rpc_url = FieldValidator.require_field(network_config, 'rpc_url', f"network.{network}")

        # Validate RPC URL format (basic check)
        if not isinstance(rpc_url, str) or not rpc_url.startswith(('http://', 'https://', 'ws://', 'wss://')):
            raise ValueError(f"Invalid RPC URL format for network '{network}': {rpc_url}")

        return network_config

    @staticmethod
    def validate_api_config(config: Dict, service_name: str) -> Dict:
        """Validate API configuration with no fallbacks.

        Args:
            config: API configuration
            service_name: Service name

        Returns:
            Validated API config

        Raises:
            ValueError: If API config is incomplete
        """
        if service_name not in config:
            raise ValueError(f"API service '{service_name}' not configured")

        service_config = config[service_name]
        if not isinstance(service_config, dict):
            raise ValueError(f"API service '{service_name}' config must be a dictionary")

        # Require API key
        api_key = FieldValidator.require_field(service_config, 'api_key', f"api.{service_name}")

        if not isinstance(api_key, str) or len(api_key.strip()) == 0:
            raise ValueError(f"Invalid API key for service '{service_name}'")

        return service_config
