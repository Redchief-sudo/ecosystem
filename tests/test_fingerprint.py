"""
Tests for the ecosystem fingerprint system.
"""

import pytest
import json
import copy
from datetime import datetime
from core.fingerprint import (
    CreatorFingerprint,
    GuardianFingerprint,
    BehavioralFingerprint,
    EcosystemFingerprint,
    FingerprintGenerator,
    FingerprintValidator,
    FingerprintVersion,
    generate_fingerprint,
    validate_fingerprint
)


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        'trading': {
            'mode': 'paper',
            'paper_trading': True,
            'security_level': 'high',
            'max_position_size': 1000.0,
            'max_slippage': 0.01,
            'risk_tolerance': 0.6,
            'rebalance_frequency': 'hourly',
            'max_drawdown': 0.15,
            'max_leverage': 2.0,
            'position_limit': 5
        },
        'networks': {
            'ethereum': {'rpc_url': 'https://eth.example.com'},
            'polygon': {'rpc_url': 'https://polygon.example.com'},
            'arbitrum': {'rpc_url': 'https://arbitrum.example.com'}
        },
        'strategies': {
            'elite_momentum': {'enabled': True, 'weight': 1.5},
            'mean_reversion': {'enabled': True, 'weight': 1.0},
            'elite_breakout': {'enabled': False, 'weight': 0.5}
        },
        'scanners': {
            'dexscreener': {'enabled': True},
            'birdeye': {'enabled': True}
        },
        'ai': {
            'enabled': True,
            'decision_method': 'ensemble'
        }
    }


def test_creator_fingerprint_immutable(sample_config):
    """Test that CreatorFingerprint is immutable."""
    generator = FingerprintGenerator()
    fp = generator.generate_from_config(sample_config)
    
    # Try to modify - should raise error
    with pytest.raises((AttributeError, Exception)):
        fp.creator.system_id = "modified"


def test_creator_fingerprint_hash_deterministic(sample_config):
    """Test that creator fingerprint hash is deterministic."""
    generator = FingerprintGenerator()
    
    fp1 = generator.generate_from_config(sample_config, deterministic=True)
    fp2 = generator.generate_from_config(sample_config, deterministic=True)
    
    assert fp1.creator.compute_hash() == fp2.creator.compute_hash()


def test_guardian_fingerprint_captures_security(sample_config):
    """Test that guardian fingerprint captures security settings."""
    generator = FingerprintGenerator()
    fp = generator.generate_from_config(sample_config)
    
    assert fp.guardian.paper_trading_mode is True
    assert fp.guardian.security_level == 'high'
    assert fp.guardian.max_position_size == 1000.0
    assert fp.guardian.max_slippage == 0.01
    assert 'ethereum' in fp.guardian.allowed_networks
    assert fp.guardian.risk_limits['max_drawdown'] == 0.15


def test_behavioral_fingerprint_captures_patterns(sample_config):
    """Test that behavioral fingerprint captures execution patterns."""
    generator = FingerprintGenerator()
    fp = generator.generate_from_config(sample_config)
    
    assert fp.behavioral.execution_mode == 'paper'
    assert fp.behavioral.risk_tolerance == 0.6
    assert fp.behavioral.rebalance_frequency == 'hourly'
    assert fp.behavioral.decision_method == 'ensemble'
    assert 'dexscreener' in fp.behavioral.scanner_ids
    assert 'elite_momentum' in fp.behavioral.strategy_weights


def test_composite_hash_combines_all_fingerprints(sample_config):
    """Test that composite hash combines all individual fingerprints."""
    generator = FingerprintGenerator()
    fp = generator.generate_from_config(sample_config)
    
    # Composite hash should be deterministic
    assert len(fp.composite_hash) == 64  # SHA256 hex length
    assert fp.composite_hash == fp._compute_composite_hash()


def test_fingerprint_integrity_verification(sample_config):
    """Test fingerprint integrity verification."""
    generator = FingerprintGenerator()
    fp = generator.generate_from_config(sample_config)
    
    assert fp.verify_integrity() is True


def test_fingerprint_reproducibility(sample_config):
    """Test that fingerprints are reproducible from same config."""
    generator = FingerprintGenerator()
    
    fp1 = generator.generate_from_config(sample_config, deterministic=True)
    fp2 = generator.generate_from_config(sample_config, deterministic=True)
    
    # Individual hashes should match
    assert fp1.creator.compute_hash() == fp2.creator.compute_hash()
    assert fp1.guardian.compute_hash() == fp2.guardian.compute_hash()
    assert fp1.behavioral.compute_hash() == fp2.behavioral.compute_hash()
    
    # Composite hashes should match
    assert fp1.composite_hash == fp2.composite_hash


def test_fingerprint_changes_with_config(sample_config):
    """Test that fingerprint changes when config changes."""
    generator = FingerprintGenerator()
    
    fp1 = generator.generate_from_config(sample_config, deterministic=True)
    
    # Modify config
    modified_config = copy.deepcopy(sample_config)
    modified_config['trading']['max_position_size'] = 2000.0
    
    fp2 = generator.generate_from_config(modified_config, deterministic=True)
    
    # Guardian fingerprint should differ
    assert fp1.guardian.compute_hash() != fp2.guardian.compute_hash()
    
    # Composite hash should differ
    assert fp1.composite_hash != fp2.composite_hash


def test_fingerprint_validation_success(sample_config):
    """Test successful fingerprint validation."""
    fp = generate_fingerprint(sample_config)
    
    validator = FingerprintValidator()
    assert validator.validate(fp) is True


def test_fingerprint_validation_checks_version(sample_config):
    """Test that validation checks fingerprint version."""
    fp = generate_fingerprint(sample_config)
    
    # Modify version to invalid value
    object.__setattr__(fp, 'fingerprint_version', '99.0.0')
    
    validator = FingerprintValidator()
    assert validator.validate(fp) is False


def test_fingerprint_to_dict_serialization(sample_config):
    """Test fingerprint serialization to dictionary."""
    fp = generate_fingerprint(sample_config)
    
    fp_dict = fp.to_dict()
    
    assert 'fingerprint_version' in fp_dict
    assert 'generated_at' in fp_dict
    assert 'creator' in fp_dict
    assert 'guardian' in fp_dict
    assert 'behavioral' in fp_dict
    assert 'composite_hash' in fp_dict
    assert 'individual_hashes' in fp_dict
    
    # Check individual hashes present
    assert 'creator' in fp_dict['individual_hashes']
    assert 'guardian' in fp_dict['individual_hashes']
    assert 'behavioral' in fp_dict['individual_hashes']


def test_fingerprint_json_serializable(sample_config):
    """Test that fingerprint can be serialized to JSON."""
    fp = generate_fingerprint(sample_config)
    
    fp_dict = fp.to_dict()
    json_str = json.dumps(fp_dict, indent=2)
    
    # Should be valid JSON
    reloaded = json.loads(json_str)
    assert reloaded['composite_hash'] == fp.composite_hash


def test_multiple_fingerprints_reproducibility():
    """Test reproducibility across multiple identical configs."""
    config = {
        'trading': {'mode': 'paper', 'paper_trading': True},
        'networks': {'ethereum': {}},
        'strategies': {'momentum': {'weight': 1.0}},
        'ai': {'decision_method': 'simple'}
    }
    
    # Use deterministic mode for reproducibility
    generator = FingerprintGenerator()
    fingerprints = [generator.generate_from_config(config, deterministic=True) for _ in range(10)]
    
    # All should have same composite hash
    composite_hashes = [fp.composite_hash for fp in fingerprints]
    assert len(set(composite_hashes)) == 1


def test_strategy_weights_extraction(sample_config):
    """Test extraction of strategy weights."""
    fp = generate_fingerprint(sample_config)
    
    weights = fp.behavioral.strategy_weights
    assert weights['elite_momentum'] == 1.5
    assert weights['mean_reversion'] == 1.0
    assert weights['elite_breakout'] == 0.5


def test_enabled_features_detection(sample_config):
    """Test detection of enabled features."""
    fp = generate_fingerprint(sample_config)
    
    features = fp.creator.enabled_features
    assert 'paper_trading' in features
    assert 'ai_decisions' in features
    assert 'token_scanning' in features
    assert 'strategy_engine' in features


def test_network_count_correct(sample_config):
    """Test that network count is correct."""
    fp = generate_fingerprint(sample_config)
    
    assert fp.creator.network_count == 3


def test_strategy_count_correct(sample_config):
    """Test that strategy count is correct."""
    fp = generate_fingerprint(sample_config)
    
    assert fp.creator.strategy_count == 3


def test_allowed_networks_sorted(sample_config):
    """Test that allowed networks are sorted for determinism."""
    fp = generate_fingerprint(sample_config)
    
    networks = fp.guardian.allowed_networks
    assert networks == sorted(networks)


def test_scanner_ids_sorted(sample_config):
    """Test that scanner IDs are sorted for determinism."""
    fp = generate_fingerprint(sample_config)
    
    scanner_ids = fp.behavioral.scanner_ids
    assert scanner_ids == sorted(scanner_ids)


def test_config_hash_excludes_volatile_fields():
    """Test that config hash excludes volatile fields like api_keys."""
    config1 = {
        'trading': {'mode': 'paper'},
        'networks': {},
        'strategies': {},
        'api_keys': {'infura': 'key1'}
    }
    
    config2 = {
        'trading': {'mode': 'paper'},
        'networks': {},
        'strategies': {},
        'api_keys': {'infura': 'key2'}
    }
    
    fp1 = generate_fingerprint(config1)
    fp2 = generate_fingerprint(config2)
    
    # Config hash should be same (api_keys excluded)
    assert fp1.creator.config_hash == fp2.creator.config_hash


def test_fingerprint_validator_is_reproducible():
    """Test FingerprintValidator.is_reproducible method."""
    config = {
        'trading': {'mode': 'paper'},
        'networks': {'ethereum': {}},
        'strategies': {},
        'ai': {}
    }
    
    generator = FingerprintGenerator()
    fp1 = generator.generate_from_config(config, deterministic=True)
    fp2 = generator.generate_from_config(config, deterministic=True)
    
    validator = FingerprintValidator()
    assert validator.is_reproducible(fp1, fp2) is True


def test_system_id_deterministic(sample_config):
    """Test that system ID is deterministic."""
    generator = FingerprintGenerator()
    
    fp1 = generator.generate_from_config(sample_config, deterministic=True)
    fp2 = generator.generate_from_config(sample_config, deterministic=True)
    
    assert fp1.creator.system_id == fp2.creator.system_id
    assert len(fp1.creator.system_id) == 16  # 16 hex characters


def test_timestamp_format_iso8601(sample_config):
    """Test that timestamps are in ISO 8601 format."""
    fp = generate_fingerprint(sample_config)
    
    # Should be parseable as ISO format
    dt = datetime.fromisoformat(fp.generated_at)
    assert isinstance(dt, datetime)
    
    dt = datetime.fromisoformat(fp.creator.build_timestamp)
    assert isinstance(dt, datetime)


def test_convenience_functions(sample_config):
    """Test convenience functions generate_fingerprint and validate_fingerprint."""
    fp = generate_fingerprint(sample_config)
    
    assert validate_fingerprint(fp) is True
    assert isinstance(fp, EcosystemFingerprint)
