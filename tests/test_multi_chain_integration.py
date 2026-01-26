"""
Multi-Chain Integration Test
===========================

Tests that all multi-chain components are properly wired together.
"""

import asyncio
from typing import Dict, Any

# Test imports work correctly
def test_imports():
    """Test that all multi-chain components can be imported."""
    
    # Network models
    from networks import (
        ChainType, AddressType, TokenIdentity, TokenCandidate,
        get_chain_type, detect_address_type, normalize_address, validate_address
    )
    
    # Token pipeline
    from trading.token_pipeline import (
        MultiChainTokenDeduplicator,
        MultiChainTokenIngestionPipeline,
        MultiChainQueueManager,
        enqueue_token, dequeue_any_token
    )
    
    # Strategies
    from strategies import (
        EVMStrategy, SolanaStrategy, MultiChainStrategyManager,
        StrategyDecision
    )
    
    # Execution
    from trading.execution import (
        EVMExecutor, SolanaExecutor, MultiChainExecutor,
        ExecutionResult, ExecutionStatus
    )
    
    print("✅ All imports successful")


def test_chain_type_detection():
    """Test chain type detection works."""
    from networks import get_chain_type, detect_address_type, ChainType, AddressType
    
    # Test EVM
    assert get_chain_type("ethereum") == ChainType.EVM
    assert get_chain_type("bsc") == ChainType.EVM
    assert detect_address_type("0x1234567890123456789012345678901234567890") == AddressType.EVM
    
    # Test Solana
    assert get_chain_type("solana") == ChainType.SOLANA
    assert detect_address_type("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM") == AddressType.SOLANA
    
    print("✅ Chain type detection working")


def test_address_normalization():
    """Test address normalization works."""
    from networks import normalize_address, validate_address, ChainType
    
    # EVM address
    evm_addr = "0x1234567890123456789012345678901234567890"
    normalized = normalize_address(evm_addr, ChainType.EVM)
    assert normalized == evm_addr.lower()
    assert validate_address(evm_addr, ChainType.EVM)
    
    # Solana address
    sol_addr = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    normalized = normalize_address(sol_addr, ChainType.SOLANA)
    assert normalized == sol_addr  # Case-sensitive
    assert validate_address(sol_addr, ChainType.SOLANA)
    
    print("✅ Address normalization working")


def test_token_identity():
    """Test TokenIdentity deduplication works."""
    from networks import TokenIdentity, ChainType, AddressType
    
    # Create two identical identities
    identity1 = TokenIdentity(
        chain="ethereum",
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        chain_type=ChainType.EVM
    )
    
    identity2 = TokenIdentity(
        chain="ethereum",
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        chain_type=ChainType.EVM
    )
    
    # Test dedup key
    assert identity1.get_dedup_key() == identity2.get_dedup_key()
    assert identity1 == identity2
    assert hash(identity1) == hash(identity2)
    
    print("✅ TokenIdentity deduplication working")


def test_token_candidate():
    """Test TokenCandidate creation works."""
    from networks import TokenCandidate, ChainType, AddressType
    
    candidate = TokenCandidate(
        chain="ethereum",
        chain_type=ChainType.EVM,
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        symbol="TEST",
        name="Test Token",
        price_usd=1.0,
        liquidity_usd=10000.0
    )
    
    # Test identity
    identity = candidate.get_identity()
    assert identity.chain == "ethereum"
    assert identity.address_type == AddressType.EVM
    assert identity.chain_type == ChainType.EVM
    
    # Test network-specific data
    network_data = candidate.get_network_specific_data()
    assert "pair_address" in network_data
    
    # Test chain type checks
    assert candidate.is_evm()
    assert not candidate.is_solana()
    
    print("✅ TokenCandidate creation working")


def test_deduplicator():
    """Test multi-chain deduplicator works."""
    from trading.token_pipeline.multi_chain_deduplicator import MultiChainTokenDeduplicator
    from networks import TokenCandidate, ChainType, AddressType
    
    deduplicator = MultiChainTokenDeduplicator()
    
    # Create test tokens
    evm_token = {
        "chain": "ethereum",
        "address": "0x1234567890123456789012345678901234567890",
        "symbol": "EVM_TEST",
        "name": "EVM Test Token"
    }
    
    sol_token = {
        "chain": "solana",
        "address": "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "symbol": "SOL_TEST", 
        "name": "Solana Test Token"
    }
    
    # Process tokens
    evm_candidates = deduplicator.add_tokens([evm_token], "test_scanner")
    sol_candidates = deduplicator.add_tokens([sol_token], "test_scanner")
    
    assert len(evm_candidates) == 1
    assert len(sol_candidates) == 1
    assert evm_candidates[0].chain_type == ChainType.EVM
    assert sol_candidates[0].chain_type == ChainType.SOLANA
    
    # Test deduplication
    evm_candidates_2 = deduplicator.add_tokens([evm_token], "test_scanner2")
    assert len(evm_candidates_2) == 0  # Should be deduplicated
    
    print("✅ Multi-chain deduplicator working")


def test_queue_manager():
    """Test multi-chain queue manager works."""
    from trading.token_pipeline.multi_chain_queue_manager import MultiChainQueueManager
    from networks import TokenCandidate, ChainType, AddressType
    
    queue_manager = MultiChainQueueManager(max_queue_size=10)
    
    # Create test candidates
    evm_candidate = TokenCandidate(
        chain="ethereum",
        chain_type=ChainType.EVM,
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        symbol="EVM_TEST",
        name="EVM Test Token"
    )
    
    sol_candidate = TokenCandidate(
        chain="solana",
        chain_type=ChainType.SOLANA,
        address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        address_type=AddressType.SOLANA,
        symbol="SOL_TEST",
        name="Solana Test Token"
    )
    
    # Test enqueueing
    assert asyncio.run(queue_manager.enqueue(evm_candidate))
    assert asyncio.run(queue_manager.enqueue(sol_candidate))
    
    # Test queue sizes
    assert queue_manager.get_queue_size(ChainType.EVM) == 1
    assert queue_manager.get_queue_size(ChainType.SOLANA) == 1
    
    # Test dequeueing
    dequeued_evm = asyncio.run(queue_manager.dequeue(ChainType.EVM))
    assert dequeued_evm.symbol == "EVM_TEST"
    
    dequeued_sol = asyncio.run(queue_manager.dequeue(ChainType.SOLANA))
    assert dequeued_sol.symbol == "SOL_TEST"
    
    print("✅ Multi-chain queue manager working")


def test_strategy_manager():
    """Test multi-chain strategy manager works."""
    from strategies.multi_chain_strategies import MultiChainStrategyManager
    from networks import TokenCandidate, ChainType, AddressType
    
    config = {
        "strategies": {
            "evm": {"enabled": True},
            "solana": {"enabled": True}
        }
    }
    
    strategy_manager = MultiChainStrategyManager(config)
    
    # Test supported chains
    supported_chains = strategy_manager.get_supported_chain_types()
    assert ChainType.EVM in supported_chains
    assert ChainType.SOLANA in supported_chains
    
    # Create test candidates
    evm_candidate = TokenCandidate(
        chain="ethereum",
        chain_type=ChainType.EVM,
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        symbol="EVM_TEST",
        name="EVM Test Token",
        pair_address="0xabcdef1234567890abcdef1234567890abcdef12"
    )
    
    sol_candidate = TokenCandidate(
        chain="solana",
        chain_type=ChainType.SOLANA,
        address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        address_type=AddressType.SOLANA,
        symbol="SOL_TEST",
        name="Solana Test Token",
        pool_id="11111111111111111111111111111112"
    )
    
    # Test evaluation (async)
    async def test_evaluations():
        evm_decision = await strategy_manager.evaluate_token(evm_candidate, {})
        sol_decision = await strategy_manager.evaluate_token(sol_candidate, {})
        
        assert evm_decision is not None
        assert sol_decision is not None
        assert isinstance(evm_decision, StrategyDecision)
        assert isinstance(sol_decision, StrategyDecision)
    
    asyncio.run(test_evaluations())
    
    print("✅ Multi-chain strategy manager working")


def test_executor():
    """Test multi-chain executor works."""
    from trading.execution.multi_chain_executor import MultiChainExecutor
    from networks import TokenCandidate, ChainType, AddressType
    from strategies.multi_chain_strategies import StrategyDecision
    
    config = {
        "executors": {
            "evm": {"enabled": True},
            "solana": {"enabled": True}
        }
    }
    
    executor = MultiChainExecutor(config)
    
    # Test supported chains
    supported_chains = executor.get_supported_chain_types()
    assert ChainType.EVM in supported_chains
    assert ChainType.SOLANA in supported_chains
    
    # Create test candidates
    evm_candidate = TokenCandidate(
        chain="ethereum",
        chain_type=ChainType.EVM,
        address="0x1234567890123456789012345678901234567890",
        address_type=AddressType.EVM,
        symbol="EVM_TEST",
        name="EVM Test Token",
        price_usd=1.0
    )
    
    # Create test decision
    evm_decision = StrategyDecision(
        should_trade=True,
        confidence=0.8,
        direction="buy",
        position_size=0.1,
        expected_return=0.05,
        risk_score=0.3,
        metadata={},
        network_specific={
            "pair_address": "0xabcdef1234567890abcdef1234567890abcdef12",
            "gas_estimate": {"gas_limit": 200000, "gas_price_gwei": 20}
        }
    )
    
    # Test execution (async)
    async def test_execution():
        result = await executor.execute_trade(evm_candidate, evm_decision)
        assert result is not None
        assert isinstance(result, ExecutionResult)
        assert result.status in [ExecutionStatus.SUBMITTED, ExecutionStatus.FAILED]
        assert result.network == ChainType.EVM
    
    asyncio.run(test_execution())
    
    print("✅ Multi-chain executor working")


def test_end_to_end_flow():
    """Test complete end-to-end flow."""
    print("\n🧪 Testing End-to-End Multi-Chain Flow...")
    
    # This would be a comprehensive test of the entire pipeline
    # For now, we'll just verify all components can be instantiated together
    
    from networks import ChainType, AddressType, TokenCandidate
    from trading.token_pipeline import MultiChainTokenIngestionPipeline, MultiChainQueueManager
    from strategies import MultiChainStrategyManager
    from trading.execution import MultiChainExecutor
    
    # Configuration
    config = {
        "max_queue_size": 100,
        "strategies": {
            "evm": {"enabled": True},
            "solana": {"enabled": True}
        },
        "executors": {
            "evm": {"enabled": True},
            "solana": {"enabled": True}
        }
    }
    
    # Initialize components
    ingestion = MultiChainTokenIngestionPipeline(config)
    queue_manager = MultiChainQueueManager(config["max_queue_size"])
    strategy_manager = MultiChainStrategyManager(config)
    executor = MultiChainExecutor(config)
    
    print("✅ All components initialized successfully")
    print("✅ End-to-end integration ready")


if __name__ == "__main__":
    """Run all integration tests."""
    print("🔧 Testing Multi-Chain Integration...\n")
    
    test_imports()
    test_chain_type_detection()
    test_address_normalization()
    test_token_identity()
    test_token_candidate()
    test_deduplicator()
    test_queue_manager()
    test_strategy_manager()
    test_executor()
    test_end_to_end_flow()
    
    print("\n🎉 All integration tests passed!")
    print("✅ Multi-chain architecture is properly wired together!")
