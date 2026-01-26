# test_hybrid_scanner.py
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def test_hybrid_scanner():
    """Test the hybrid scanner with memory manager integration"""
    try:
        from scanners.hybrid_scanner import EliteHybridScanner
        from utils.memory import MemoryManager

        # Get absolute path to the database
        db_path = Path(__file__).parent.parent / 'data' / 'ecosystem.db'
        logger.debug(f"Database path: {db_path}")
        logger.debug(f"Database exists: {db_path.exists()}")
        logger.debug(f"Absolute path: {db_path.absolute()}")
        
        # Check database permissions
        logger.debug(f"Readable: {os.access(db_path, os.R_OK)}")
        logger.debug(f"Writable: {os.access(db_path, os.W_OK)}")
        
        # Initialize memory manager with correct database path
        logger.info("Initializing MemoryManager...")
        memory = MemoryManager(db_path=str(db_path.absolute()))
        
        # Log token information
        token_count = len(memory.tokens)
        logger.info(f"Loaded {token_count} tokens from database")
        
        # Log tokens by chain
        chains = {}
        for token in memory.tokens.values():
            chains[token.chain] = chains.get(token.chain, 0) + 1
        logger.info(f"Tokens by chain: {chains}")
        
        # Debug: Show sample tokens for each chain
        logger.info("\nSample tokens from memory:")
        for chain in list(chains.keys())[:3]:  # Show first 3 chains
            chain_tokens = [t for t in memory.tokens.values() if t.chain == chain]
            if chain_tokens:
                token = chain_tokens[0]
                logger.info(f"  {chain}: {token.symbol} - ${token.price:.6f} - Liquidity: ${token.liquidity_usd:,.2f}")
        
        # Debug: Test get_recent_tokens directly
        recent_tokens = memory.get_recent_tokens(hours=8760)  # Get all tokens (1+ year)
        logger.info(f"\nget_recent_tokens returned {len(recent_tokens)} tokens")
        if recent_tokens:
            logger.info("Sample recent tokens:")
            for token in recent_tokens[:3]:
                logger.info(f"  {token.symbol} ({token.chain}): price=${token.price:.6f}, liquidity=${token.liquidity_usd:,.2f}")
        
        if token_count == 0:
            logger.error("No tokens found in database")
            return False
            
        # Initialize the scanner with memory manager
        scanner = EliteHybridScanner(
            config={
                'min_liquidity_usd': 0,  # No minimum liquidity for testing
                'min_volume_24h_usd': 0,  # No minimum volume for testing
                'min_holders': 0,  # No minimum holders for testing
                'max_tokens_per_scan': 50,
                'enabled_networks': list(chains.keys()),
                'rpc_urls': {
                    'ethereum': 'https://eth.llamarpc.com',
                    'bsc': 'https://bsc-dataseed.binance.org/',
                    'polygon': 'https://polygon-rpc.com/',
                    # Add other RPC endpoints as needed
                },
                'data_freshness_hours': 8760  # Use all tokens (1+ year)
            },
            memory=memory
        )
        
        # Initialize the scanner
        if not await scanner.initialize():
            logger.error("Failed to initialize scanner")
            return False
            
        logger.info("Scanner initialized successfully")
        
        # Test scanning each network with tokens
        for chain in chains.keys():
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"Testing network: {chain.upper()}")
                logger.info(f"{'='*50}")
                
                # Scan the network
                logger.info(f"Scanning {chain}...")
                tokens = await scanner.scan(chain)
                
                if not tokens:
                    logger.warning(f"No tokens found on {chain}")
                    continue
                
                logger.info(f"Found {len(tokens)} tokens on {chain}")
                
                # Display sample tokens
                logger.info("\nSample tokens:")
                for i, token in enumerate(tokens[:3]):  # Show first 3 tokens
                    try:
                        token_data = token.to_dict() if hasattr(token, 'to_dict') else vars(token)
                        
                        logger.info(f"{i+1}. {token_data.get('symbol', 'N/A')} - {token_data.get('name', 'N/A')}")
                        logger.info(f"   Address: {token_data.get('address', 'N/A')}")
                        logger.info(f"   Chain: {token_data.get('chain_name', 'N/A')}")
                        logger.info(f"   Price: ${token_data.get('price', 0):.8f}")
                        logger.info(f"   Liquidity: ${token_data.get('liquidity_usd', 0):,.2f}")
                        logger.info(f"   Volume 24h: ${token_data.get('volume_24h', 0):,.2f}")
                        
                        # Log score if available
                        if 'score' in token_data.get('metadata', {}):
                            score = token_data['metadata']['score']
                            logger.info(f"   Score: {score.get('overall', 0):.2f}")
                        logger.info("")
                    except Exception as e:
                        logger.error(f"Error displaying token {i+1}: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"Error scanning {chain}: {str(e)}", exc_info=True)
                continue
        
        return True
        
    except ImportError as e:
        logger.error(f"Import error: {str(e)}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("Starting Hybrid Scanner Test with Database Integration")
    success = asyncio.run(test_hybrid_scanner())
    
    if success:
        logger.info("\n✅ Test completed successfully!")
    else:
        logger.error("\n❌ Test failed. See logs for details.")
