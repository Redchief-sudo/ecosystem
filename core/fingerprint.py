"""
Ecosystem Fingerprint System

Provides deterministic, immutable, and versioned fingerprints for:
- Creator fingerprints: System identity and provenance
- Guardian fingerprints: Security and integrity markers
- Behavioral fingerprints: Execution patterns and characteristics
"""

import hashlib
import json
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum


class FingerprintType(Enum):
    """Types of fingerprints in the ecosystem."""
    CREATOR = "creator"
    GUARDIAN = "guardian"
    BEHAVIORAL = "behavioral"


class FingerprintVersion(Enum):
    """Fingerprint schema versions."""
    V1 = "1.0.0"


@dataclass(frozen=True)
class CreatorFingerprint:
    """
    Creator fingerprint - System identity and provenance.
    
    Captures:
    - System version and build info
    - Configuration hash
    - Network configuration
    - Strategy configuration
    """
    version: str
    system_id: str
    build_timestamp: str
    config_hash: str
    network_count: int
    strategy_count: int
    enabled_features: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of creator fingerprint."""
        # Sort dictionary for deterministic ordering
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass(frozen=True)
class GuardianFingerprint:
    """
    Guardian fingerprint - Security and integrity markers.
    
    Captures:
    - Security settings
    - Integrity checks
    - Access controls
    - Compliance markers
    """
    version: str
    security_level: str
    paper_trading_mode: bool
    max_position_size: float
    max_slippage: float
    allowed_networks: List[str]
    risk_limits: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of guardian fingerprint."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass(frozen=True)
class BehavioralFingerprint:
    """
    Behavioral fingerprint - Execution patterns and characteristics.
    
    Captures:
    - Trading patterns
    - Risk profile
    - Execution preferences
    - Performance characteristics
    """
    version: str
    execution_mode: str
    strategy_weights: Dict[str, float]
    risk_tolerance: float
    rebalance_frequency: str
    scanner_ids: List[str]
    decision_method: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    def compute_hash(self) -> str:
        """Compute deterministic hash of behavioral fingerprint."""
        data = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()


@dataclass
class EcosystemFingerprint:
    """
    Complete ecosystem fingerprint combining all fingerprint types.
    
    Immutable once generated, versioned for schema evolution.
    """
    fingerprint_version: str
    generated_at: str
    creator: CreatorFingerprint
    guardian: GuardianFingerprint
    behavioral: BehavioralFingerprint
    composite_hash: str = field(init=False)
    
    def __post_init__(self):
        """Compute composite hash after initialization."""
        # Use object.__setattr__ to set frozen field
        object.__setattr__(self, 'composite_hash', self._compute_composite_hash())
    
    def _compute_composite_hash(self) -> str:
        """Compute composite hash from all fingerprints."""
        combined = f"{self.creator.compute_hash()}{self.guardian.compute_hash()}{self.behavioral.compute_hash()}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'fingerprint_version': self.fingerprint_version,
            'generated_at': self.generated_at,
            'creator': self.creator.to_dict(),
            'guardian': self.guardian.to_dict(),
            'behavioral': self.behavioral.to_dict(),
            'composite_hash': self.composite_hash,
            'individual_hashes': {
                'creator': self.creator.compute_hash(),
                'guardian': self.guardian.compute_hash(),
                'behavioral': self.behavioral.compute_hash()
            }
        }
    
    def verify_integrity(self) -> bool:
        """Verify fingerprint integrity by recomputing hash."""
        return self.composite_hash == self._compute_composite_hash()


class FingerprintGenerator:
    """
    Generates deterministic fingerprints from ecosystem configuration.
    
    Thread-safe and stateless for reproducible fingerprint generation.
    """
    
    @staticmethod
    def generate_from_config(config: Dict[str, Any], deterministic: bool = False) -> EcosystemFingerprint:
        """
        Generate complete ecosystem fingerprint from configuration.
        
        Args:
            config: Ecosystem configuration dictionary
            deterministic: If True, use fixed timestamps for reproducibility
            
        Returns:
            EcosystemFingerprint with all components
        """
        # Use fixed timestamp for deterministic mode
        if deterministic:
            timestamp = "2000-01-01T00:00:00+00:00"
        else:
            timestamp = datetime.now(timezone.utc).isoformat()
        
        # Extract configuration sections
        trading_config = config.get('trading', {})
        networks_config = config.get('networks', {})
        strategies_config = config.get('strategies', {})
        ai_config = config.get('ai', {})
        
        # Generate creator fingerprint
        creator = CreatorFingerprint(
            version=FingerprintVersion.V1.value,
            system_id=FingerprintGenerator._generate_system_id(config),
            build_timestamp=timestamp,
            config_hash=FingerprintGenerator._hash_config(config),
            network_count=len(networks_config),
            strategy_count=len(strategies_config),
            enabled_features=FingerprintGenerator._extract_features(config)
        )
        
        # Generate guardian fingerprint
        guardian = GuardianFingerprint(
            version=FingerprintVersion.V1.value,
            security_level=trading_config.get('security_level', 'standard'),
            paper_trading_mode=trading_config.get('paper_trading', False),
            max_position_size=float(trading_config.get('max_position_size', 1000.0)),
            max_slippage=float(trading_config.get('max_slippage', 0.01)),
            allowed_networks=sorted(networks_config.keys()),
            risk_limits=FingerprintGenerator._extract_risk_limits(trading_config)
        )
        
        # Generate behavioral fingerprint
        behavioral = BehavioralFingerprint(
            version=FingerprintVersion.V1.value,
            execution_mode=trading_config.get('mode', 'paper'),
            strategy_weights=FingerprintGenerator._extract_strategy_weights(strategies_config),
            risk_tolerance=float(trading_config.get('risk_tolerance', 0.5)),
            rebalance_frequency=trading_config.get('rebalance_frequency', 'hourly'),
            scanner_ids=sorted(config.get('scanners', {}).keys()),
            decision_method=ai_config.get('decision_method', 'ensemble')
        )
        
        # Combine into ecosystem fingerprint
        return EcosystemFingerprint(
            fingerprint_version=FingerprintVersion.V1.value,
            generated_at=timestamp,
            creator=creator,
            guardian=guardian,
            behavioral=behavioral
        )
    
    @staticmethod
    def _generate_system_id(config: Dict[str, Any]) -> str:
        """Generate deterministic system ID from config."""
        # Use config hash as base for system ID
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()[:16]
    
    @staticmethod
    def _hash_config(config: Dict[str, Any]) -> str:
        """Compute deterministic hash of configuration."""
        # Remove volatile fields before hashing
        stable_config = {k: v for k, v in config.items() if k not in ['logs', 'api_keys']}
        config_str = json.dumps(stable_config, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()
    
    @staticmethod
    def _extract_features(config: Dict[str, Any]) -> List[str]:
        """Extract enabled features from config."""
        features = []
        
        if config.get('trading', {}).get('paper_trading'):
            features.append('paper_trading')
        if config.get('ai', {}).get('enabled'):
            features.append('ai_decisions')
        if config.get('scanners'):
            features.append('token_scanning')
        if config.get('strategies'):
            features.append('strategy_engine')
        
        return sorted(features)
    
    @staticmethod
    def _extract_risk_limits(trading_config: Dict[str, Any]) -> Dict[str, Any]:
        """Extract risk limit configuration."""
        return {
            'max_drawdown': trading_config.get('max_drawdown', 0.2),
            'max_leverage': trading_config.get('max_leverage', 1.0),
            'position_limit': trading_config.get('position_limit', 10)
        }
    
    @staticmethod
    def _extract_strategy_weights(strategies_config: Dict[str, Any]) -> Dict[str, float]:
        """Extract strategy weights from config."""
        weights = {}
        for strategy_id, strategy_cfg in strategies_config.items():
            if isinstance(strategy_cfg, dict):
                weights[strategy_id] = float(strategy_cfg.get('weight', 1.0))
        return weights


class FingerprintValidator:
    """
    Validates fingerprints for integrity and reproducibility.
    """
    
    @staticmethod
    def validate(fingerprint: EcosystemFingerprint) -> bool:
        """
        Validate fingerprint integrity.
        
        Args:
            fingerprint: Ecosystem fingerprint to validate
            
        Returns:
            True if valid, False otherwise
        """
        # Check version
        if fingerprint.fingerprint_version != FingerprintVersion.V1.value:
            return False
        
        # Check integrity
        if not fingerprint.verify_integrity():
            return False
        
        # Check timestamp format
        try:
            datetime.fromisoformat(fingerprint.generated_at)
        except ValueError:
            return False
        
        # Check all hashes are present and valid hex
        try:
            int(fingerprint.composite_hash, 16)
            int(fingerprint.creator.compute_hash(), 16)
            int(fingerprint.guardian.compute_hash(), 16)
            int(fingerprint.behavioral.compute_hash(), 16)
        except ValueError:
            return False
        
        return True
    
    @staticmethod
    def is_reproducible(fp1: EcosystemFingerprint, fp2: EcosystemFingerprint) -> bool:
        """
        Check if two fingerprints are reproducible (have same composite hash).
        
        Args:
            fp1: First fingerprint
            fp2: Second fingerprint
            
        Returns:
            True if fingerprints match
        """
        return fp1.composite_hash == fp2.composite_hash


# Singleton instance for easy access
_fingerprint_generator = FingerprintGenerator()
_fingerprint_validator = FingerprintValidator()


def generate_fingerprint(config: Dict[str, Any]) -> EcosystemFingerprint:
    """
    Generate ecosystem fingerprint from configuration.
    
    Args:
        config: Ecosystem configuration
        
    Returns:
        Complete ecosystem fingerprint
    """
    return _fingerprint_generator.generate_from_config(config)


def validate_fingerprint(fingerprint: EcosystemFingerprint) -> bool:
    """
    Validate fingerprint integrity.
    
    Args:
        fingerprint: Fingerprint to validate
        
    Returns:
        True if valid
    """
    return _fingerprint_validator.validate(fingerprint)
