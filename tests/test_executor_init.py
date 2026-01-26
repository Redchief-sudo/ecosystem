#!/usr/bin/env python3
"""Test executor initialization"""

import sys

sys.path.insert(0, '/home/damien/ecosystem')

from bootstrap.path_manager import get_path_manager
# Initialize logging FIRST
from utils.logger import get_logger, setup_logging

# Set up logging for this test run
path_manager = get_path_manager()
log_file = path_manager.get_path('logs') / 'test_executor_debug.log'
print(f"📝 Setting up logging to: {log_file}")

# Ensure logs directory exists
path_manager.ensure_directory_exists('logs')

setup_logging(
    log_level='DEBUG',
    log_file=log_file,
    max_bytes=10*1024*1024,
    backup_count=5
)

logger = get_logger('test_executor')
logger.info("🚀 Starting TradeExecutor initialization test")
logger.info(f"📝 Log file location: {log_file}")

from network.network_manager import NetworkManager
from router.hybrid_router_manager import HybridRouterManager
from trading.trade_executor import TradeExecutor
from config import load_config

print("🔧 Testing TradeExecutor initialization...")

try:
    # Load config
    logger.info("Loading configuration...")
    config = load_config()
    logger.info("✅ Configuration loaded successfully")
    print("✅ Config loaded")
    
    # Check wallet credentials
    wallet_config = config.get('wallets', {}).get('executor', {})
    logger.info(f"Wallet credentials - Private key: {'SET' if wallet_config.get('private_key') else 'MISSING'}")
    logger.info(f"Wallet credentials - Address: {'SET' if wallet_config.get('address') else 'MISSING'}")
    print(f"✅ Private key: {'SET' if wallet_config.get('private_key') else 'MISSING'}")
    print(f"✅ Address: {'SET' if wallet_config.get('address') else 'MISSING'}")
    
    # Initialize network manager
    logger.info("Initializing NetworkManager...")
    network_manager = NetworkManager(config)
    logger.info("✅ NetworkManager initialized successfully")
    print("✅ Network manager initialized")
    
    # Initialize router manager
    logger.info("Initializing HybridRouterManager...")
    router_manager = HybridRouterManager(network_manager, config)
    logger.info("✅ HybridRouterManager initialized successfully")
    print("✅ Router manager initialized")
    
    # Initialize executor
    logger.info("Initializing TradeExecutor...")
    executor = TradeExecutor(
        config=config,
        network_manager=network_manager,
        router_manager=router_manager
    )
    logger.info("✅ TradeExecutor initialized successfully!")
    logger.info(f"Wallet address: {executor.wallet_address}")
    logger.info(f"Paper trading mode: {executor.paper_trading}")
    print("✅ TradeExecutor initialized successfully!")
    print(f"✅ Wallet address: {executor.wallet_address}")
    print(f"✅ Paper trading: {executor.paper_trading}")
    
except Exception as e:
    logger.error(f"❌ Error during initialization: {e}")
    logger.error("Full traceback:", exc_info=True)
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
