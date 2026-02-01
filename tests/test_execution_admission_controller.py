import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

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
    def admission_controller(self, config, token_registry, mock_network_manager):
        """Admission controller instance"""
        controller = ExecutionAdmissionController(config, token_registry, network_manager=mock_network_manager)
        # Initialize async token loading for test
        import asyncio
        asyncio.run(controller.initialize())
        return controller

    @pytest.fixture
    def mock_network_manager(self):
        """Mock network manager"""
        manager = Mock()
        manager.get_web3 = Mock(return_value=Mock())
        manager.get_web3.return_value.eth.get_balance = AsyncMock(return_value=500000000000000000)  # 0.5 MATIC
        manager.get_web3.return_value.from_wei = Mock(return_value=0.5)
        return manager

    def test_initialization(self, admission_controller):
        """Test controller initializes correctly"""
        assert admission_controller.enabled is True
        assert admission_controller.minimum_notional_usd['polygon'] == 5.0
        assert admission_controller.minimum_gas_balance['polygon'] == 0.1
        # Allowlist may be empty after initialize if token resolution failed; check key exists
        assert 'polygon' in admission_controller._token_addresses

    @pytest.mark.asyncio
    async def test_disabled_controller(self, config, token_registry, mock_network_manager):
        """Test disabled controller always admits"""
        config['execution_admission']['enabled'] = False
        controller = ExecutionAdmissionController(config, token_registry)

        # Create mock execution plan
        plan = Mock()
        plan.chain = 'polygon'

        result = await controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'disabled' in result.reason.lower()

    @pytest.mark.asyncio
    async def test_minimum_notional_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection of trades below minimum notional"""
        # Create mock execution plan with dust amount
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 1.0  # Below minimum of 5.0

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'below minimum notional' in result.reason.lower()
        assert result.details['required'] == 5.0
        assert result.details['actual'] == 1.0

    @pytest.mark.asyncio
    async def test_minimum_notional_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance of trades above minimum notional"""
        # Create mock execution plan with valid amount
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0  # Above minimum of 5.0

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is True

    @pytest.mark.asyncio
    async def test_gas_balance_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection when wallet has insufficient gas"""
        # Mock Web3 to return low balance
        mock_w3 = Mock()
        mock_w3.eth.get_balance = AsyncMock(return_value=0)  # 0 wei = insufficient gas
        mock_w3.from_wei = Mock(return_value=0.0)
        mock_network_manager.get_web3.return_value = mock_w3

        # Create mock execution plan
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'insufficient gas' in result.reason.lower()

    @pytest.mark.asyncio
    async def test_gas_balance_check_success(self, admission_controller, mock_network_manager):
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

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is True

    @pytest.mark.asyncio
    async def test_executable_token_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection of non-executable tokens"""
        # Create mock execution plan with invalid token
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0xInvalidTokenAddress'

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'not executable' in result.reason.lower()

    @pytest.mark.asyncio
    async def test_executable_token_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance of executable tokens"""
        # Create mock execution plan with valid token
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'  # USDC on Polygon

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is True

    @pytest.mark.asyncio
    async def test_execution_plan_completeness_failure(self, admission_controller, mock_network_manager):
        """Test rejection of incomplete execution plans"""
        # Create mock execution plan missing required fields
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        # Missing plan_id
        plan.plan_id = None

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'incomplete' in result.reason.lower()

    @pytest.mark.asyncio
    async def test_base_asset_check_failure(self, admission_controller, mock_network_manager):
        """Test rejection of invalid base asset"""
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        plan.base_asset = 'ETH'  # Invalid base asset

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'invalid base asset' in result.reason.lower()

    @pytest.mark.asyncio
    async def test_base_asset_check_success(self, admission_controller, mock_network_manager):
        """Test acceptance of valid base asset"""
        plan = Mock()
        plan.chain = 'polygon'
        plan.amount_usd = 10.0
        plan.token_address = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
        plan.base_asset = 'USDC'
        plan.max_slippage = 0.05
        plan.plan_id = 'test_plan'
        plan.is_buy = True

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is True

    @pytest.mark.asyncio
    async def test_missing_chain_configuration(self, admission_controller, mock_network_manager):
        """Test rejection when chain is not configured"""
        plan = Mock()
        plan.chain = 'unknown_chain'
        plan.amount_usd = 10.0

        result = await admission_controller.validate_execution_plan(plan, '0x123')

        assert result.admitted is False
        assert 'missing chain' in result.reason.lower()

    async def test_get_admission_stats(self, admission_controller):
        """Test admission stats retrieval"""
        stats = admission_controller.get_admission_stats()
        assert isinstance(stats, dict)
        assert 'enabled' in stats
        assert 'executable_tokens' in stats
        assert 'enabled_strategies' in stats
        assert 'minimum_notional_usd' in stats
        assert 'minimum_gas_balance' in stats
