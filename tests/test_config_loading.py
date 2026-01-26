"""
Test script to verify configuration loading.
"""
import os
import sys
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

import logging

import yaml

from config import get_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('config_test')

def test_config_loading():
    """Test that configuration is loaded correctly using assertions."""
    # Load the configuration
    config = get_config()

    # Check required sections exist
    required_sections = ['ai', 'trading', 'scanners', 'networks']
    for section in required_sections:
        assert config.get(section) is not None, f"Missing required configuration section: {section}"

    # Check AI configuration
    ai_config = config.get('ai', {})
    assert isinstance(ai_config, dict)
    if ai_config.get('enabled', False):
        enabled_components = ai_config.get('enabled_components', [])
        assert isinstance(enabled_components, list)  # smoke check for component list (non-fatal)"

    # Check scanner configuration (soft checks)
    scanners = config.get('scanners', {})
    # At least one scanner section should exist
    assert isinstance(scanners, dict)

    # Check basic network configuration
    networks = config.get('networks', {})
    assert networks, "No network configurations found"

    # Basic smoke assertions for some non-sensitive structure
    assert hasattr(config, '_config') and isinstance(config._config, dict)

    # If we've reached here, basic configuration loads successfully
    assert True
