#!/bin/bash

# Set environment variables for RPC URLs
export ETHEREUM_RPC_URL=${ETHEREUM_RPC_URL:-"https://eth-mainnet.g.alchemy.com/v2/your-api-key"}
export BSC_RPC_URL=${BSC_RPC_URL:-"https://bsc-dataseed.binance.org/"}
export POLYGON_RPC_URL=${POLYGON_RPC_URL:-"https://polygon-rpc.com/"}
export ARBITRUM_RPC_URL=${ARBITRUM_RPC_URL:-"https://arb1.arbitrum.io/rpc"}

# Create logs directory if it doesn't exist
mkdir -p logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/scanner_test_${TIMESTAMP}.log"

# Print header
echo "="*70
echo "Running Scanner Test - $(date)"
echo "Logging to: ${LOG_FILE}"
echo "="*70

# Run the test with minimal configuration
python -m tests.test_scanners --config tests/test_config_minimal.yaml 2>&1 | tee -a "${LOG_FILE}"

# Print completion message
echo -e "\nTest completed. Log saved to: ${LOG_FILE}"
echo "You can view the log with: cat ${LOG_FILE}"
