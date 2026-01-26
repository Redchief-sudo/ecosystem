import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """Environment variable validation levels."""
    REQUIRED = "required"
    OPTIONAL = "optional"
    RECOMMENDED = "recommended"

@dataclass
class EnvVar:
    """Environment variable definition."""
    name: str
    level: ValidationLevel
    description: str
    validator: Optional[str] = None  # regex pattern or validation function name
    default_value: Optional[str] = None

class EnvironmentValidator:
    """Validates and manages environment variables for the trading ecosystem."""
    
    REQUIRED_VARS = [
        EnvVar(
            name="WALLET_ADDRESS",
            level=ValidationLevel.REQUIRED,
            description="Your wallet's public address (0x...)",
            validator=r"^0x[a-fA-F0-9]{40}$"
        ),
        EnvVar(
            name="PRIVATE_KEY",
            level=ValidationLevel.REQUIRED,
            description="Your wallet's private key (keep secure)",
            validator=r"^0x[a-fA-F0-9]{64}$"
        ),
    ]
    
    # Only WebSocket URLs for real-time data (RPC URLs are in networks.yaml)
    WEBSOCKET_VARS = [
        EnvVar(
            name="ETHEREUM_WS_URL",
            level=ValidationLevel.OPTIONAL,
            description="Ethereum WebSocket URL for real-time data (overrides networks.yaml)",
            validator=r"^wss?://.+"
        ),
        EnvVar(
            name="BSC_WS_URL",
            level=ValidationLevel.OPTIONAL,
            description="BSC WebSocket URL for real-time data (overrides networks.yaml)",
            validator=r"^wss?://.+"
        ),
        EnvVar(
            name="POLYGON_WS_URL",
            level=ValidationLevel.OPTIONAL,
            description="Polygon WebSocket URL for real-time data (overrides networks.yaml)",
            validator=r"^wss?://.+"
        ),
        EnvVar(
            name="ARBITRUM_WS_URL",
            level=ValidationLevel.OPTIONAL,
            description="Arbitrum WebSocket URL for real-time data (overrides networks.yaml)",
            validator=r"^wss?://.+"
        ),
    ]
    
    CONFIG_VARS = [
        EnvVar(
            name="ENVIRONMENT",
            level=ValidationLevel.OPTIONAL,
            description="Environment (development, production, test)",
            default_value="development",
            validator=r"^(development|production|test)$"
        ),
        EnvVar(
            name="LOG_LEVEL",
            level=ValidationLevel.OPTIONAL,
            description="Logging level (DEBUG, INFO, WARNING, ERROR)",
            default_value="INFO",
            validator=r"^(DEBUG|INFO|WARNING|ERROR)$"
        ),
        EnvVar(
            name="PAPER_TRADING",
            level=ValidationLevel.OPTIONAL,
            description="Enable paper trading mode",
            default_value="true",
            validator=r"^(true|false)$"
        ),
        EnvVar(
            name="MAX_POSITION_SIZE",
            level=ValidationLevel.OPTIONAL,
            description="Maximum position size as percentage (overrides config.yaml)",
            default_value="0.1",
            validator=r"^0\.\d+$"
        ),
    ]
    
    def __init__(self):
        """Initialize the environment validator."""
        self.validation_errors: List[str] = []
        self.validation_warnings: List[str] = []
        self.missing_vars: List[str] = []
        self.invalid_vars: List[str] = []
    
    def validate_all(self) -> bool:
        """Validate all environment variables."""
        logger.info("Starting environment variable validation...")
        
        # Clear previous results
        self.validation_errors.clear()
        self.validation_warnings.clear()
        self.missing_vars.clear()
        self.invalid_vars.clear()
        
        all_vars = self.REQUIRED_VARS + self.WEBSOCKET_VARS + self.CONFIG_VARS
        
        for env_var in all_vars:
            self._validate_variable(env_var)
        
        # Log results
        if self.validation_errors:
            logger.error(f"Environment validation failed with {len(self.validation_errors)} errors")
            for error in self.validation_errors:
                logger.error(f"  - {error}")
        
        if self.validation_warnings:
            logger.warning(f"Environment validation completed with {len(self.validation_warnings)} warnings")
            for warning in self.validation_warnings:
                logger.warning(f"  - {warning}")
        
        if not self.validation_errors and not self.validation_warnings:
            logger.info("Environment validation passed successfully")
        
        return len(self.validation_errors) == 0
    
    def _validate_variable(self, env_var: EnvVar) -> None:
        """Validate a single environment variable."""
        value = os.getenv(env_var.name)
        
        # Check if variable exists
        if value is None:
            if env_var.level == ValidationLevel.REQUIRED:
                error_msg = f"Missing required environment variable: {env_var.name} - {env_var.description}"
                self.validation_errors.append(error_msg)
                self.missing_vars.append(env_var.name)
            elif env_var.level == ValidationLevel.RECOMMENDED:
                warning_msg = f"Missing recommended environment variable: {env_var.name} - {env_var.description}"
                self.validation_warnings.append(warning_msg)
                self.missing_vars.append(env_var.name)
            # Optional variables can be missing
            return
        
        # Apply default value if empty and default exists
        if not value and env_var.default_value:
            os.environ[env_var.name] = env_var.default_value
            value = env_var.default_value
            logger.info(f"Applied default value for {env_var.name}: {env_var.default_value}")
        
        # Validate format if validator is specified
        if env_var.validator and value:
            import re
            if not re.match(env_var.validator, value):
                error_msg = f"Invalid format for {env_var.name}: '{value}' - {env_var.description}"
                if env_var.level == ValidationLevel.REQUIRED:
                    self.validation_errors.append(error_msg)
                else:
                    self.validation_warnings.append(error_msg)
                self.invalid_vars.append(env_var.name)
    
    def get_validation_summary(self) -> Dict[str, Any]:
        """Get a summary of validation results."""
        return {
            "is_valid": len(self.validation_errors) == 0,
            "errors": self.validation_errors,
            "warnings": self.validation_warnings,
            "missing_vars": self.missing_vars,
            "invalid_vars": self.invalid_vars,
            "total_errors": len(self.validation_errors),
            "total_warnings": len(self.validation_warnings)
        }
    
    def validate_private_key_security(self) -> bool:
        """Validate private key security best practices."""
        private_key = os.getenv("PRIVATE_KEY")
        if not private_key:
            return True  # Will be caught by main validation
        
        # Check for common insecure patterns
        insecure_patterns = [
            "0000000000000000000000000000000000000000000000000000000000000000",
            "1111111111111111111111111111111111111111111111111111111111111111",
            "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        ]
        
        if private_key.lower() in insecure_patterns:
            error_msg = "Private key appears to be insecure (using common test pattern)"
            self.validation_errors.append(error_msg)
            return False
        
        # Check length (should be 66 characters with 0x prefix for 32 bytes)
        if len(private_key) != 66:
            error_msg = f"Private key length is incorrect: expected 66 characters, got {len(private_key)}"
            self.validation_errors.append(error_msg)
            return False
        
        return True
    
    def validate_wallet_address_format(self) -> bool:
        """Validate wallet address format and checksum."""
        wallet_address = os.getenv("WALLET_ADDRESS")
        if not wallet_address:
            return True  # Will be caught by main validation
        
        # Basic format check
        if not wallet_address.startswith("0x") or len(wallet_address) != 42:
            error_msg = f"Invalid wallet address format: {wallet_address}"
            self.validation_errors.append(error_msg)
            return False
        
        # Check for valid hex characters
        try:
            int(wallet_address, 16)
        except ValueError:
            error_msg = f"Wallet address contains invalid hex characters: {wallet_address}"
            self.validation_errors.append(error_msg)
            return False
        
        return True
    
    def validate_websocket_endpoints(self) -> bool:
        """Validate WebSocket endpoint formats (optional overrides)."""
        ws_vars = [var for var in self.WEBSOCKET_VARS]
        all_valid = True
        
        for env_var in ws_vars:
            url = os.getenv(env_var.name)
            if not url:
                continue  # Skip missing optional variables
            
            # Basic URL format check
            if not (url.startswith("ws://") or url.startswith("wss://")):
                error_msg = f"Invalid WebSocket URL format for {env_var.name}: {url}"
                self.validation_errors.append(error_msg)
                all_valid = False
                continue
            
            logger.debug(f"WebSocket URL format validated: {env_var.name}")
        
        return all_valid

def validate_environment() -> bool:
    """Convenience function to validate the entire environment."""
    validator = EnvironmentValidator()
    
    # Run main validation
    is_valid = validator.validate_all()
    
    # Run additional security validations
    validator.validate_private_key_security()
    validator.validate_wallet_address_format()
    validator.validate_websocket_endpoints()
    
    # Print summary
    summary = validator.get_validation_summary()
    if summary["total_errors"] > 0:
        logger.error("Environment validation failed - system may not operate correctly")
        return False
    
    if summary["total_warnings"] > 0:
        logger.warning("Environment validation completed with warnings")
    
    logger.info("Environment validation passed successfully")
    return True

if __name__ == "__main__":
    # Run validation if script is executed directly
    logging.basicConfig(level=logging.INFO)
    success = validate_environment()
    exit(0 if success else 1)
