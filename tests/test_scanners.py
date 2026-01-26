"""
Test script for verifying scanner functionality.
This script tests all scanner components and logs the results to a file.
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
sys.path.append(str(PROJECT_ROOT))

from scanners.dex_screener_scanner import DexScreenerScanner
from scanners.enhanced_onchain_scanner import EnhancedOnchainScanner
from scanners.hybrid_scanner import EliteHybridScanner
from scanners.mempool_scanner import MempoolScannerUltra  # Fixed import
# Import scanner components
from scanners.scan_director import ScanDirector
from utils.config_manager import ConfigManager
from utils.memory import MemoryManager


def setup_logging(log_level=logging.INFO):
    """Set up logging configuration.
    
    Args:
        log_level: Logging level (default: logging.INFO)
    """
    LOG_DIR = PROJECT_ROOT / 'logs'
    LOG_DIR.mkdir(exist_ok=True)
    LOG_FILE = LOG_DIR / f'scanner_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
    
    # Set up the root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    
    # Set log level for specific loggers
    loggers = [
        'scanner_test',
        'scanners.dex_screener_scanner',
        'scanners.enhanced_onchain_scanner',
        'scanners.mempool_scanner',
        'scanners.hybrid_scanner',
        'scanners.scan_director',
        'utils.memory',
        'utils.config_manager'
    ]
    
    for logger_name in loggers:
        logging.getLogger(logger_name).setLevel(log_level)
    
    return logging.getLogger('scanner_test')

# Parse command line arguments
def parse_args():
    parser = argparse.ArgumentParser(description='Run scanner tests')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                      help='Path to config file')
    parser.add_argument('--log-level', type=str, default='INFO',
                      choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='Logging level')
    return parser.parse_args()

# Initialize logger with default level
logger = setup_logging()

class ScannerTester:
    """Class to test scanner functionality."""
    
    def __init__(self, config):
        """Initialize the scanner tester."""
        self.config = config
        self.memory = MemoryManager()
        self.scanners = []
        self.scan_director = None
        
    async def initialize(self):
        """Initialize all scanners and the scan director."""
        logger.info("Initializing scanners...")
        enabled_networks = self.config.get('networks', {}).get('enabled', [])
        
        # Initialize individual scanners
        scanner_configs = {
            'dex_screener': (DexScreenerScanner, 'DexScreener Scanner'),
            'onchain': (EnhancedOnchainScanner, 'Enhanced On-chain Scanner'),
            'mempool': (MempoolScannerUltra, 'Mempool Scanner'),
            'hybrid': (EliteHybridScanner, 'Elite Hybrid Scanner'),
        }
        
        for scanner_key, (scanner_class, scanner_name) in scanner_configs.items():
            if self.config.get(f'scanners.{scanner_key}.enabled', True):
                try:
                    # Different scanners have different constructor signatures
                    if scanner_key == 'dex_screener':
                        scanner = scanner_class(
                            config=self.config,
                            memory_manager=self.memory
                        )
                    elif scanner_key == 'mempool':
                        scanner = scanner_class(
                            config=self.config,
                            memory=self.memory
                        )
                    else:
                        scanner = scanner_class(
                            config=self.config,
                            enabled_networks=enabled_networks,
                            memory=self.memory
                        )
                    self.scanners.append(scanner)
                    logger.info(f"✅ Initialized {scanner_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize {scanner_name}: {e}", exc_info=True)
        
        # Initialize scan director
        self.scan_director = ScanDirector(
            network_manager=None,  # Pass None since we don't have a network manager
            memory=self.memory,
            config=self.config
        )
        await self.scan_director.initialize()
        logger.info("✅ Initialized Scan Director")
    
    async def test_scan(self):
        """Test scanning functionality."""
        if not self.scan_director:
            logger.error("Scan director not initialized")
            return False
        
        logger.info("\n" + "="*50)
        logger.info("STARTING SCANNER TEST")
        logger.info("="*50)
        
        try:
            # Run a scan
            logger.info("\nRunning scanner test...")
            results = await self.scan_director.scan_all()
            
            # Log results
            logger.info("\n" + "="*50)
            logger.info("SCAN RESULTS")
            logger.info("="*50)
            
            if not results:
                logger.warning("No results returned from scan")
                return False
                
            # Log summary of found tokens
            token_count = len(results)
            logger.info(f"Found {token_count} tokens")
            
            # Log first few tokens as samples
            sample_size = min(5, token_count)
            logger.info(f"\nSample tokens (first {sample_size}):")
            for i, token in enumerate(results[:sample_size], 1):
                logger.info(f"{i}. {token.get('symbol', 'N/A')} "
                           f"({token.get('network', 'N/A')}): "
                           f"${token.get('price_usd', 'N/A')} "
                           f"Liquidity: ${token.get('liquidity_usd', 'N/A')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error during scan: {e}", exc_info=True)
            return False
    
    async def cleanup(self):
        """Clean up resources."""
        logger.info("\nCleaning up...")
        if self.scan_director and hasattr(self.scan_director, 'cleanup'):
            try:
                await self.scan_director.cleanup()
                logger.info("✅ Cleaned up scan director")
            except Exception as e:
                logger.error(f"❌ Error cleaning up scan director: {e}")

async def main():
    """Main test function."""
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Set up logging with the specified level
        log_level = getattr(logging, args.log_level)
        global logger
        logger = setup_logging(log_level)
        logger.info(f"Starting scanner test with log level: {args.log_level}")
        
        # Load configuration
        config_path = args.config
        logger.info(f"Loading configuration from: {config_path}")
        
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return 1
            
        tester = None
        try:
            # Initialize config manager
            logger.debug("Initializing ConfigManager...")
            config_manager = ConfigManager(config_path)
            
            # Get the configuration dictionary
            config = {}
            if hasattr(config_manager, '_config'):
                config = config_manager._config
            
            if not config:
                logger.error("Failed to load configuration: Empty config")
                return 1
                
            logger.debug(f"Successfully loaded config with {len(config)} top-level keys")
            
            # Initialize scanner tester with the config
            logger.info("Initializing scanner tester...")
            tester = ScannerTester(config)
            await tester.initialize()
            
            # Run tests
            logger.info("Starting scanner tests...")
            success = await tester.test_scan()
            
            return 0 if success else 1
            
        except Exception as e:
            logger.error(f"Error during test execution: {e}", exc_info=True)
            return 1
            
        finally:
            # Clean up resources
            if tester and hasattr(tester, 'cleanup'):
                try:
                    await tester.cleanup()
                except Exception as e:
                    logger.error(f"Error during cleanup: {e}", exc_info=True)
        
    except Exception as e:
        logger.error(f"Fatal error during scanner test: {e}", exc_info=True)
        return 1
        
    logger.info(f"\nTest log saved to: {LOG_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
