# Multi-Chain Integration Guide
# =============================

This guide shows how to integrate the new multi-chain architecture into your trading system.

## Overview

The new multi-chain architecture replaces the EVM-centric approach with true multi-network support:

- **Chain-aware token models** with proper address type handling
- **Network-specific normalizers** for each blockchain
- **Chain-type aware deduplication** to prevent cross-chain conflicts
- **Separate queues per network** to avoid mixing incompatible formats
- **Network-specific strategies** tailored to each blockchain's characteristics
- **Dedicated execution modules** for each network type

## Quick Start

### 1. Update Your Main Application

```python
# main.py
import asyncio
from networks.multi_chain_models import ChainType
from trading.token_pipeline.multi_chain_ingestion import initialize_multi_chain_ingestion_pipeline
from trading.token_pipeline.multi_chain_queue_manager import initialize_queue_manager
from strategies.multi_chain_strategies import initialize_multi_chain_strategy_manager
from trading.execution.multi_chain_executor import initialize_multi_chain_executor

async def main():
    # Load multi-chain configuration
    config = load_config("config/multi_chain_config.yaml")
    
    # Initialize multi-chain components
    ingestion_pipeline = initialize_multi_chain_ingestion_pipeline(config["multi_chain_ingestion"])
    queue_manager = initialize_queue_manager(config["multi_chain_ingestion"]["max_queue_size"])
    strategy_manager = initialize_multi_chain_strategy_manager(config)
    executor = initialize_multi_chain_executor(config)
    
    # Start the trading loop
    await run_multi_chain_trading_loop(config)

async def run_multi_chain_trading_loop(config):
    """Main trading loop with multi-chain support."""
    from trading.token_pipeline.multi_chain_queue_manager import dequeue_any_token
    from strategies.multi_chain_strategies import get_multi_chain_strategy_manager
    from trading.execution.multi_chain_executor import get_multi_chain_executor
    
    strategy_manager = get_multi_chain_strategy_manager()
    executor = get_multi_chain_executor()
    
    while True:
        try:
            # Dequeue from any network (EVM prioritized)
            candidate = await dequeue_any_token(timeout=1.0)
            if not candidate:
                continue
            
            print(f"Processing {candidate.symbol} on {candidate.chain_type.value}")
            
            # Get market data (network-specific)
            market_data = await get_market_data(candidate)
            
            # Evaluate with network-specific strategy
            decision = await strategy_manager.evaluate_token(candidate, market_data)
            if not decision or not decision.should_trade:
                continue
            
            # Execute with network-specific executor
            result = await executor.execute_trade(candidate, decision)
            print(f"Execution result: {result.status.value}")
            
        except Exception as e:
            print(f"Error in trading loop: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
```

### 2. Update Your Scanners

```python
# scanners/multi_chain_scanner.py
from trading.token_pipeline.multi_chain_ingestion import ingest_multi_chain_scan_results

class MultiChainScanner:
    async def scan_and_ingest(self):
        # Scan multiple networks
        for chain in ["ethereum", "bsc", "solana"]:
            raw_tokens = await self.scan_chain(chain)
            
            # Ingest with automatic chain type detection
            result = await ingest_multi_chain_scan_results(
                scanner_name=self.__class__.__name__,
                raw_tokens=raw_tokens,
                scan_id=f"{chain}_{int(time.time())}"
            )
            
            print(f"Ingested {result['enqueued']} tokens from {chain}")
```

### 3. Add New Network Support

To add support for a new network (e.g., Aptos):

#### Step 1: Update Models
```python
# networks/multi_chain_models.py
class ChainType(Enum):
    # ... existing chains ...
    APTOS = "aptos"  # Already added

class AddressType(Enum):
    # ... existing types ...
    APTOS = "aptos"  # Already added
```

#### Step 2: Add Normalizer
```python
# networks/chain_normalizers.py
class AptosNormalizer(ChainNormalizer):
    APTOS_ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{64}$")
    
    @staticmethod
    def normalize(address: str) -> str:
        if not AptosNormalizer.validate(address):
            raise ValueError(f"Invalid Aptos address format: {address}")
        return address.lower()
    
    @staticmethod
    def validate(address: str) -> bool:
        return bool(AptosNormalizer.APTOS_ADDRESS_PATTERN.match(address.strip()))
    
    @staticmethod
    def get_address_type() -> AddressType:
        return AddressType.APTOS

# Add to MultiChainNormalizer._normalizers
ChainType.APTOS: AptosNormalizer(),
```

#### Step 3: Add Strategy
```python
# strategies/multi_chain_strategies.py
class AptosStrategy(BaseNetworkStrategy):
    def get_supported_chain_type(self) -> ChainType:
        return ChainType.APTOS
    
    def validate_candidate(self, candidate: TokenCandidate) -> bool:
        if not candidate.is_aptos():
            return False
        # Aptos-specific validation
        return True
    
    async def evaluate(self, candidate: TokenCandidate, market_data: Dict[str, Any]) -> StrategyDecision:
        # Aptos-specific evaluation logic
        return StrategyDecision(...)
```

#### Step 4: Add Executor
```python
# trading/execution/multi_chain_executor.py
class AptosExecutor(BaseNetworkExecutor):
    def get_supported_chain_type(self) -> ChainType:
        return ChainType.APTOS
    
    async def execute_trade(self, candidate: TokenCandidate, decision: StrategyDecision) -> ExecutionResult:
        # Aptos-specific execution logic
        return ExecutionResult(...)
```

## Configuration

### Environment Variables
```bash
# EVM Configuration
ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/YOUR_PROJECT_ID
ETHEREUM_PRIVATE_KEY=your_private_key_here
ETHEREUM_WALLET_ADDRESS=your_wallet_address

# Solana Configuration
SOLANA_PRIVATE_KEY=your_solana_private_key
SOLANA_WALLET_ADDRESS=your_solana_wallet_address

# Aptos Configuration (when enabled)
APTOS_PRIVATE_KEY=your_aptos_private_key
APTOS_WALLET_ADDRESS=your_aptos_wallet_address
```

### Network-Specific Settings
```yaml
# config/multi_chain_config.yaml
strategies:
  evm:
    enabled: true
    min_liquidity_usd: 1000.0
    confidence_threshold: 0.6
  
  solana:
    enabled: true
    min_liquidity_usd: 500.0
    confidence_threshold: 0.65

executors:
  evm:
    enabled: true
    max_slippage: 0.05
    max_gas_price_gwei: 100
  
  solana:
    enabled: true
    max_slippage: 0.10
```

## Migration from EVM-Only System

### Step 1: Update Token Processing
```python
# OLD (EVM-only)
from trading.token_pipeline.token_ingestion import ingest_scan_results

# NEW (Multi-chain)
from trading.token_pipeline.multi_chain_ingestion import ingest_multi_chain_scan_results
```

### Step 2: Update Token Models
```python
# OLD (EVM-only)
from trading.token_pipeline.token_candidate import TokenCandidate

# NEW (Multi-chain)
from networks.multi_chain_models import TokenCandidate, ChainType, AddressType
```

### Step 3: Update Strategy Calls
```python
# OLD (EVM-only)
from strategies.elite_strategy_manager import EliteStrategyManager

# NEW (Multi-chain)
from strategies.multi_chain_strategies import get_multi_chain_strategy_manager
```

## Testing

### Unit Tests
```python
# tests/test_multi_chain.py
import pytest
from networks.multi_chain_models import TokenCandidate, ChainType, AddressType
from networks.chain_normalizers import MultiChainNormalizer

def test_evm_address_normalization():
    addr = "0x1234567890123456789012345678901234567890"
    normalized = MultiChainNormalizer.normalize_address(addr, ChainType.EVM)
    assert normalized == addr.lower()

def test_solana_address_normalization():
    addr = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
    normalized = MultiChainNormalizer.normalize_address(addr, ChainType.SOLANA)
    assert normalized == addr  # Solana is case-sensitive

def test_chain_type_detection():
    from networks.multi_chain_models import get_chain_type
    assert get_chain_type("ethereum") == ChainType.EVM
    assert get_chain_type("solana") == ChainType.SOLANA
```

### Integration Tests
```python
# tests/test_multi_chain_integration.py
async def test_end_to_end_flow():
    # Create test token
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
    
    # Test ingestion
    from trading.token_pipeline.multi_chain_ingestion import ingest_multi_chain_scan_results
    result = await ingest_multi_chain_scan_results(
        "test_scanner",
        [{"address": candidate.address, "symbol": candidate.symbol}]
    )
    assert result["enqueued"] > 0
    
    # Test strategy evaluation
    from strategies.multi_chain_strategies import get_multi_chain_strategy_manager
    strategy_manager = get_multi_chain_strategy_manager()
    decision = await strategy_manager.evaluate_token(candidate, {})
    assert decision is not None
    
    # Test execution
    from trading.execution.multi_chain_executor import get_multi_chain_executor
    executor = get_multi_chain_executor()
    exec_result = await executor.execute_trade(candidate, decision)
    assert exec_result is not None
```

## Monitoring

### Multi-Chain Metrics
```python
# Get comprehensive stats
from trading.token_pipeline.multi_chain_ingestion import get_multi_chain_ingestion_pipeline
from trading.token_pipeline.multi_chain_queue_manager import get_queue_manager

pipeline = get_multi_chain_ingestion_pipeline()
stats = pipeline.get_ingestion_stats()

print("Multi-Chain Stats:")
print(f"Total Ingested: {stats['total_ingested']}")
print(f"Total Enqueued: {stats['total_enqueued']}")
print(f"Chain Breakdown: {stats['chain_type_stats']}")
print(f"Queue Stats: {stats['queue_stats']}")
```

### Per-Network Monitoring
```python
# Monitor specific networks
queue_manager = get_queue_manager()
evm_stats = queue_manager.get_all_stats()["evm"]
solana_stats = queue_manager.get_all_stats()["solana"]

print(f"EVM Queue Size: {evm_stats['current_size']}")
print(f"Solana Queue Size: {solana_stats['current_size']}")
```

## Troubleshooting

### Common Issues

1. **Address Format Mismatch**
   ```
   Error: Cannot normalize address for chain solana
   Solution: Ensure address format matches chain type
   ```

2. **Missing Strategy**
   ```
   Error: No strategy available for chain type: solana
   Solution: Enable strategy in config: strategies.solana.enabled: true
   ```

3. **Queue Full**
   ```
   Error: Queue full for solana, dropping token
   Solution: Increase max_queue_size or process tokens faster
   ```

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger("networks").setLevel(logging.DEBUG)
logging.getLogger("trading.token_pipeline").setLevel(logging.DEBUG)
logging.getLogger("strategies").setLevel(logging.DEBUG)
```

## Performance Considerations

- **Queue Sizes**: Monitor queue sizes to prevent memory issues
- **Cleanup**: Automatic cleanup of expired tokens and processed scans
- **Batching**: Process tokens in batches for better performance
- **Async**: All operations are async for non-blocking behavior

## Security Notes

- **Private Keys**: Store securely using environment variables
- **Network Validation**: All addresses are validated before processing
- **Rate Limiting**: Implement rate limiting for external API calls
- **Error Handling**: Comprehensive error handling prevents crashes

This architecture provides a solid foundation for true multi-chain trading while maintaining security and performance.
