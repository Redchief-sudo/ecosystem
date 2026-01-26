"""
Tests for Execution Admission Controller

Tests the admission controller's ability to prevent execution of:
- Dust trades (< minimum notional)
- Unfunded wallets (insufficient gas)
- Invalid tokens (not in allowlist)
- Incomplete execution plans
"""

from unittest.mock import AsyncMock, Mock

import pytest

from trading.execution.execution_admission_controller import (
    AdmissionResult, ExecutionAdmissionController)
from trading.token_pipeline import TokenRegistry


class TestExecutionAdmissionController:
    """Test suite for ExecutionAdmissionController"""

    @pytest.fixture
    def config(self):
        """Test configuration"""
        return {
            'execution_admission': {
                'enabled': True,
                'minimum_notional_usd': {
                    'polygon': 5.0,
                    'ethereum': 25.0,
                },
                'minimum_gas_balance': {
                    'polygon': 0.1,
                    'ethereum': 0.01,
                },
                'executable_tokens': {
                    'polygon': ['USDC', 'WMATIC'],
                    'ethereum': ['USDC', 'WETH'],
                }
            }
        }

    @pytest.fixture
    def token_registry(self):
        """Mock token registry"""
        registry = Mock(spec=TokenRegistry)
        registry.resolve_address.side_effect = lambda symbol, chain: {
            ('USDC', 'polygon'): '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174',
            ('WMATIC', 'polygon'): '0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270',
            ('USDC', 'ethereum'): '0xA0b86a33E6441e88C5F2712C3E9b74F5b8b6b8b8',
            ('WETH', 'ethereum'): '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        }.get((symbol, chain), None)
        return registry

    @pytest.fixture
    def admission_controller(self, config, token_registry):
        """Admission controller instance"""
        return ExecutionAdmissionController(config, token_registry)

    @pytest.fixture
    def mock_network_manager(self):
        """Mock network manager"""
        manager = Mock()
        manager.get_web3 = Mock(return_value=Mock())
        return manager

    def test_initialization(self, admission_controller):
        """Test controller initializes correctly"""
        assert admission_controller.enabled is True
        assert admission_controller.minimum_notional_usd['polygon'] == 5.0
        assert admission_controller.minimum_gas_balance['polygon'] == 0.1
        assert 'USDC' in admission_controller._token_addresses['polygon']

    def test_disabled_controller(self, config, token_registry, mock_network_manager):
        """Test disabled controller always admits"""
        config['execution_admission']['enabled'] = False
        controller = ExecutionAdmissionController(config, token_registry)

        # Create mock execution plan
        plan = Mock()
        plan.chain = 'polygon'

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is True
        assert result.reason == "Admission control disabled"

    def test_minimum_notional_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection of trades below minimum notional"""
        # Create mock execution plan with dust amount
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 1.0  # Below minimum of 5.0

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'below minimum notional' in result.reason
        assert result.details['required'] == 5.0
        assert result.details['actual'] == 1.0

    def test_minimum_notional_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance of trades above minimum notional"""
        # Create mock execution plan with valid amount
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0  # Above minimum of 5.0

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is True

    def test_gas_balance_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection when wallet has insufficient gas"""
        # Mock Web3 to return low balance
        mock_w3 = Mock()
        mock_w3.eth.get_balance = AsyncMock(return_value=0)  # 0 wei = insufficient gas
        mock_network_manager.get_web3.return_value = mock_w3

        # Create mock execution plan
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'insufficient gas balance' in result.reason.lower()

    def test_gas_balance_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance when wallet has sufficient gas"""
        # Mock Web3 to return sufficient balance (0.5 MATIC in wei)
        mock_w3 = Mock()
        mock_w3.eth.get_balance = AsyncMock(return_value=500000000000000000)  # 0.5 MATIC
        mock_w3.from_wei = Mock(return_value=0.5)
        mock_network_manager.get_web3.return_value = mock_w3

        # Create mock execution plan
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is True

    def test_executable_token_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection of non-executable tokens"""
        # Create mock execution plan with invalid token
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0xInvalidTokenAddress'

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'not in executable allowlist' in result.reason

    def test_executable_token_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance of executable tokens"""
        # Create mock execution plan with valid token
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'  # USDC on Polygon

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is True

    def test_execution_plan_completeness_failure(self, admission_controller, mock_network_manager):
        """Test rejection of incomplete execution plans"""
        # Create mock execution plan missing required fields
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        # Missing plan_id
        plan.plan_id = None

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'missing required fields' in result.reason

    def test_base_asset_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection when base asset is not USDC"""
        # Create mock execution plan with wrong base asset
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        plan.plan_id = 'test_plan'
        plan.base_asset = 'ETH'  # Wrong base asset

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'must specify USDC as base asset' in result.reason

    def test_base_asset_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance when base asset is USDC"""
        # Create mock execution plan with correct base asset
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        plan.plan_id = 'test_plan'
        plan.base_asset = 'USDC'  # Correct base asset

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is True

    def test_missing_chain_configuration(self, admission_controller, mock_network_manager):
        """Test rejection when chain is not configured"""
        # Create mock execution plan for unsupported chain
        plan = Mock()
        plan.chain = 'unsupported_chain'
        plan.amount_usd = 10.0

        result = pytest.asyncio.run(
            controller.validate_execution_plan(plan, '0x123', mock_network_manager)
        )

        assert result.admitted is False
        assert 'not configured for minimum notional' in result.reason

    def test_get_admission_stats(self, admission_controller):
        """Test admission statistics retrieval"""
        stats = admission_controller.get_admission_stats()

        assert stats['enabled'] is True
        assert 'polygon' in stats['chains_configured']
        assert stats['minimum_notionals']['polygon'] == 5.0
        assert stats['minimum_gas_balances']['polygon'] == 0.1
        assert stats['executable_tokens_per_chain']['polygon'] == 2  # USDC, WMATIC
